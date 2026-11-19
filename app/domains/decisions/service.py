"""Decisions about conversations, in shadow mode (F10).

When a customer writes, the conversation is decided a little later (one job
per conversation, so a burst of messages is decided once). The decisions are
stored and measured against what people label without seeing them; nothing in
the conversation changes. The report compares both, per question.

Who decides is the account's choice: the decisions service (Jev, or Laya
later) or the model on this server (:mod:`app.domains.decisions.local`). With
``apply_priority`` the urgency also sets the conversation's priority while it
is the AI's (:class:`PriorityOwner`): once a person, a rule or a tool changes
or clears it, the AI leaves it. A priority a person sets on their own is
their urgency label; changing the AI's is a correction, counted apart.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.contacts.models import Contact
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
    conversation_priority_to_str,
)
from app.domains.decisions import client, local
from app.domains.decisions.anonymize import anonymize
from app.domains.decisions.models import (
    OWNER_AI,
    OWNER_OTHER,
    ConversationDecision,
    DecisionSettings,
    HumanDecision,
    PriorityOwner,
)
from app.domains.decisions.questions import (
    PRIORITY_BY_URGENCY,
    TEAM_QUESTION,
    URGENCY_BY_PRIORITY,
    URGENCY_QUESTION,
    as_service_questions,
    clean,
    defaults,
    team_options,
)
from app.domains.teams.models import Team
from app.domains.usage.models import KIND_AI, UsageRecord
from app.domains.users.models import AccountUser, User

log = logging.getLogger(__name__)

# How many of the latest messages the service reads.
STATE_MESSAGES = 12
STATE_MAX_CHARS = 6000
# The local model reads ~12 tokens a second: a shorter end of the chat.
LOCAL_STATE_MAX_CHARS = 2500
# A burst of messages is decided once, this long after the first (longer
# for the local model, which takes a minute per conversation).
DECIDE_DELAY_SECONDS = 45
LOCAL_DECIDE_DELAY_SECONDS = 120

PROVIDER_API = "api"
PROVIDER_LOCAL = "local"
PROVIDERS = (PROVIDER_API, PROVIDER_LOCAL)
# Set while the AI changes a priority, so the change isn't taken as someone
# else's (:func:`priority_changed` runs from the same event).
_applying: ContextVar[bool] = ContextVar("decisions_applying_priority", default=False)
# Jev's list price, USD per million input tokens (output is free); checked
# 2026-11-15 on its docs. A local Laya costs nothing per call.
JEV_USD_PER_MILLION_INPUT = Decimal("0.042")
USAGE_CATEGORY = "decisions"


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
async def get_row(session: AsyncSession, account_id: int) -> DecisionSettings | None:
    return await session.get(DecisionSettings, account_id)


async def _teams(session: AsyncSession, account_id: int) -> list[tuple[int, str, str | None]]:
    rows = (
        await session.exec(
            select(Team.id, Team.name, Team.description)
            .where(Team.account_id == account_id)
            .order_by(Team.name)
        )
    ).all()
    return [(int(r[0] or 0), str(r[1]), r[2]) for r in rows]


async def questions_for(
    session: AsyncSession, account_id: int, row: DecisionSettings | None = None
) -> list[dict[str, Any]]:
    """The account's questions, with the team question's options filled."""
    row = row if row is not None else await get_row(session, account_id)
    questions = [dict(q) for q in (row.questions if row and row.questions else defaults())]
    teams = team_options(await _teams(session, account_id))
    for q in questions:
        if q["key"] == TEAM_QUESTION:
            q["options"] = teams
    return questions


def provider_ready(provider: str) -> bool:
    """The installation has what this provider needs."""
    return local.configured() if provider == PROVIDER_LOCAL else client.configured()


def _model(provider: str) -> str | None:
    return local.model_name() if provider == PROVIDER_LOCAL else get_settings().decisions_model


async def present_settings(session: AsyncSession, account_id: int) -> dict[str, Any]:
    row = await get_row(session, account_id)
    provider = row.provider if row else PROVIDER_API
    return {
        "enabled": bool(row and row.enabled),
        "provider": provider,
        "providers": {p: provider_ready(p) for p in PROVIDERS},
        "configured": provider_ready(provider),
        "model": _model(provider),
        "models": {p: _model(p) for p in PROVIDERS},
        "context": (row.context if row else None) or "",
        "apply_priority": bool(row and row.apply_priority),
        "questions": await questions_for(session, account_id, row),
    }


async def save_settings(
    session: AsyncSession,
    *,
    account_id: int,
    enabled: bool,
    questions: Any | None,
    provider: str | None = None,
    context: str | None = None,
    apply_priority: bool | None = None,
) -> dict[str, Any]:
    """Raises ValueError (a short code) when the questions do not hold up.
    ``None`` keeps what was saved."""
    row = await get_row(session, account_id)
    if row is None:
        row = DecisionSettings(account_id=account_id)
    row.enabled = enabled
    if provider is not None:
        if provider not in PROVIDERS:
            raise ValueError("provider")
        row.provider = provider
    if context is not None:
        if len(context) > local.CONTEXT_MAX:
            raise ValueError("context")
        row.context = context.strip() or None
    if apply_priority is not None:
        row.apply_priority = apply_priority
    if questions is not None:
        cleaned = clean(questions)
        # The team question's options are never stored: they come from teams.
        row.questions = [
            {**q, "options": []} if q["key"] == TEAM_QUESTION else q for q in cleaned
        ]
    session.add(row)
    await session.flush()
    return await present_settings(session, account_id)


async def is_on(session: AsyncSession, account_id: int) -> bool:
    row = await get_row(session, account_id)
    return row is not None and row.enabled and provider_ready(row.provider)


async def decide_delay(session: AsyncSession, account_id: int) -> int:
    row = await get_row(session, account_id)
    if row is not None and row.provider == PROVIDER_LOCAL:
        return LOCAL_DECIDE_DELAY_SECONDS
    return DECIDE_DELAY_SECONDS


# ---------------------------------------------------------------------------
# What the service reads
# ---------------------------------------------------------------------------
async def _latest_messages(session: AsyncSession, conversation_id: int) -> list[Message]:
    rows = (
        await session.exec(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.message_type.in_((MESSAGE_TYPE_INCOMING, MESSAGE_TYPE_OUTGOING)),  # type: ignore[attr-defined]
                Message.private.is_(False),  # type: ignore[attr-defined]
                Message.content.is_not(None),  # type: ignore[union-attr]
            )
            .order_by(Message.created_at.desc(), Message.id.desc())  # type: ignore[attr-defined,union-attr]
            .limit(STATE_MESSAGES)
        )
    ).all()
    return list(reversed(rows))


async def _names(session: AsyncSession, conversation: Conversation) -> list[str]:
    """Whose names come out: the customer and everyone on the account."""
    names: list[str] = []
    if conversation.contact_id:
        contact = await session.get(Contact, conversation.contact_id)
        if contact is not None and contact.name:
            names.append(contact.name)
    agents = (
        await session.exec(
            select(User.name, User.display_name)
            .join(AccountUser, AccountUser.user_id == User.id)  # type: ignore[arg-type]
            .where(AccountUser.account_id == conversation.account_id)
        )
    ).all()
    for name, display in agents:
        names.extend(n for n in (name, display) if n)
    return names


def _transcript(messages: list[Message], names: list[str] | None = None) -> str:
    """``Cliente: …`` / ``Agente: …`` lines. With ``names``, only what people
    wrote is anonymized, never the speaker labels (an agent may well be
    called "Cliente")."""
    lines = []
    for m in messages:
        who = "Cliente" if m.message_type == MESSAGE_TYPE_INCOMING else "Agente"
        said = (m.content or "").strip()
        if names is not None:
            said = anonymize(said, names)
        if said:
            lines.append(f"{who}: {said}")
    return "\n".join(lines)


async def conversation_text(
    session: AsyncSession,
    conversation: Conversation,
    *,
    anonymized: bool = True,
    max_chars: int = STATE_MAX_CHARS,
) -> tuple[str, int | None]:
    """The latest messages as one text, and the id of the newest. Anonymized
    for the service; as written for a person labeling."""
    messages = await _latest_messages(session, conversation.id)  # type: ignore[arg-type]
    if not messages:
        return "", None
    names = await _names(session, conversation) if anonymized else None
    text = _transcript(messages, names)
    # Keep the end (the newest messages) when it is too long.
    return text[-max_chars:], messages[-1].id


# ---------------------------------------------------------------------------
# Deciding
# ---------------------------------------------------------------------------
def _cost(model: str | None, input_tokens: int) -> Decimal | None:
    if model and model.startswith("jev"):
        return (Decimal(input_tokens) * JEV_USD_PER_MILLION_INPUT / Decimal(1_000_000)).quantize(
            Decimal("0.000001")
        )
    return Decimal("0")


@dataclass
class Prepared:
    """What a decision needs, read before asking: the database is not held
    while the model thinks (a minute on the local one)."""

    account_id: int
    conversation_id: int
    provider: str
    questions: dict[str, dict[str, Any]]
    state: str
    last_message_id: int | None
    context: str
    today: str
    names: list[str]
    apply_priority: bool


async def prepare(session: AsyncSession, conversation: Conversation) -> Prepared | None:
    """None when the account has it off, nothing to ask or nothing to read."""
    account_id = conversation.account_id
    row = await get_row(session, account_id)
    if row is None or not row.enabled or not provider_ready(row.provider):
        return None
    asked = as_service_questions(await questions_for(session, account_id, row))
    if not asked:
        return None
    on_server = row.provider == PROVIDER_LOCAL
    state, last_message_id = await conversation_text(
        session, conversation, max_chars=LOCAL_STATE_MAX_CHARS if on_server else STATE_MAX_CHARS
    )
    if not state:
        return None
    return Prepared(
        account_id=account_id,
        conversation_id=conversation.id,  # type: ignore[arg-type]
        provider=row.provider,
        questions=asked,
        state=state,
        last_message_id=last_message_id,
        context=row.context or "",
        today=local.today_text(_local_now(conversation)),
        names=await _names(session, conversation),
        apply_priority=row.apply_priority,
    )


async def ask(prepared: Prepared) -> client.Decisions:
    """Raises :class:`client.DecisionsError` when the service or the model fails."""
    if prepared.provider == PROVIDER_LOCAL:
        return await local.ask(
            prepared.state, prepared.questions, context=prepared.context, today=prepared.today
        )
    return await client.ask(prepared.state, prepared.questions)


async def store(
    session: AsyncSession, prepared: Prepared, result: client.Decisions
) -> list[ConversationDecision]:
    """Keep the answers and their cost, and set the priority when asked."""
    conversation = await session.get(Conversation, prepared.conversation_id)
    if conversation is None:
        return []
    model = result.model or _model(prepared.provider)
    stored = [
        ConversationDecision(
            account_id=prepared.account_id,
            conversation_id=prepared.conversation_id,
            message_id=prepared.last_message_id,
            question=key,
            answer=answer.choice[:128],
            confidence=answer.confidence,
            probabilities=answer.probabilities or None,
            model=model,
        )
        for key, answer in result.answers.items()
        if key in prepared.questions
    ]
    for decision in stored:
        session.add(decision)
    session.add(
        UsageRecord(
            account_id=prepared.account_id,
            kind=KIND_AI,
            occurred_at=_now(),
            category=USAGE_CATEGORY,
            model=model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost=_cost(model, result.input_tokens),
            currency="USD",
        )
    )
    await session.flush()
    if prepared.apply_priority:
        # The model writes the reason from what the customer said: it goes
        # through the same anonymizer before the team reads it.
        reason = anonymize(result.reason, prepared.names) if result.reason else ""
        await _apply_priority(session, conversation, stored, model=model, reason=reason)
    return stored


async def decide(session: AsyncSession, conversation: Conversation) -> list[ConversationDecision]:
    """Prepare, ask and store in one session. Does nothing (and returns
    ``[]``) when the account has it off or nothing to ask. Raises
    :class:`client.DecisionsError` when the service fails. The worker runs
    the three steps apart (:mod:`app.workers.decisions`)."""
    prepared = await prepare(session, conversation)
    if prepared is None:
        return []
    return await store(session, prepared, await ask(prepared))


async def newer_message(session: AsyncSession, prepared: Prepared) -> bool:
    """The customer wrote after what the decision read."""
    newest = (
        await session.exec(
            select(func.max(Message.id)).where(
                Message.conversation_id == prepared.conversation_id,
                Message.message_type == MESSAGE_TYPE_INCOMING,
                Message.private.is_(False),  # type: ignore[attr-defined]
            )
        )
    ).one()
    return newest is not None and (
        prepared.last_message_id is None or int(newest) > prepared.last_message_id
    )


def _local_now(conversation: Conversation) -> datetime:
    """Now, in the inbox's zone: "today" for the business's rules."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    name = getattr(conversation.inbox, "timezone", None) or "UTC"
    try:
        return datetime.now(ZoneInfo(name))
    except (ZoneInfoNotFoundError, ValueError):
        return _now()


async def _apply_priority(
    session: AsyncSession,
    conversation: Conversation,
    stored: list[ConversationDecision],
    *,
    model: str | None,
    reason: str,
) -> None:
    """The urgency becomes the priority, with a line saying so, while the
    priority is the AI's: never one someone else set, changed or cleared
    (:class:`PriorityOwner`). The conversation row is locked meanwhile, so a
    person's change at the same moment waits instead of being undone."""
    from app.domains.conversations.activities import create_activity_message
    from app.domains.conversations.service import toggle_priority

    urgency = next((d for d in stored if d.question == URGENCY_QUESTION), None)
    level = PRIORITY_BY_URGENCY.get(urgency.answer) if urgency is not None else None
    if level is None:
        return
    await session.refresh(conversation, ["priority"], with_for_update=True)
    current = conversation_priority_to_str(conversation.priority)
    owner = await session.get(PriorityOwner, conversation.id)
    if owner is None and current is not None:
        return  # set before: someone else's
    if owner is not None and owner.owner != OWNER_AI:
        return
    if current == level:
        return
    token = _applying.set(True)
    try:
        await toggle_priority(session, conversation=conversation, priority=level)
    finally:
        _applying.reset(token)
    if owner is None:
        owner = PriorityOwner(
            conversation_id=conversation.id,
            account_id=conversation.account_id,
            owner=OWNER_AI,
        )
    owner.ai_level = level
    session.add(owner)
    await session.flush()
    values = {"model": model or "IA", "level": t(DEFAULT_LOCALE, f"decisions.level.{level}")}
    content = (
        t(DEFAULT_LOCALE, "decisions.priority_set_because", reason=reason, **values)
        if reason
        else t(DEFAULT_LOCALE, "decisions.priority_set", **values)
    )
    await create_activity_message(session, conversation=conversation, content=content)


async def priority_changed(session: AsyncSession, conversation: Conversation) -> None:
    """Someone other than the AI changed the priority (a person, a rule, a
    tool): the AI leaves it alone from now on. A person who sets it on
    their own, where the AI had not set one, gives their urgency label;
    changing the AI's priority is a correction, counted apart in the report
    (the person saw the AI's pick)."""
    if _applying.get():
        return
    row = await get_row(session, conversation.account_id)
    if row is None or not row.enabled:
        return
    from app.core.current import current_user_ctx

    level = conversation_priority_to_str(conversation.priority)
    owner = await session.get(PriorityOwner, conversation.id)
    saw_the_ai = owner is not None and owner.ai_level is not None
    if owner is None:
        owner = PriorityOwner(
            conversation_id=conversation.id,
            account_id=conversation.account_id,
            owner=OWNER_OTHER,
        )
    elif owner.owner == OWNER_AI:
        owner.corrected = True
        owner.corrected_level = level
    owner.owner = OWNER_OTHER
    session.add(owner)
    user = current_user_ctx.get()
    option = URGENCY_BY_PRIORITY.get(level or "")
    if user is not None and option is not None and not saw_the_ai:
        questions = await questions_for(session, conversation.account_id, row)
        if option in _urgency_options(questions):
            label = (
                await session.exec(
                    select(HumanDecision).where(
                        HumanDecision.conversation_id == conversation.id,
                        HumanDecision.question == URGENCY_QUESTION,
                    )
                )
            ).first()
            if label is None:
                label = HumanDecision(
                    account_id=conversation.account_id,
                    conversation_id=conversation.id,
                    question=URGENCY_QUESTION,
                    answer=option,
                )
            label.answer = option
            label.user_id = user.id
            session.add(label)
    await session.flush()


async def enqueue_decide(conversation_id: int, *, delay_seconds: int = DECIDE_DELAY_SECONDS) -> None:
    """Decide this conversation a little later, off the request. A second
    message before then joins the same job (same id)."""
    settings = get_settings()
    if settings.app_env == "test":
        return
    from arq import create_pool
    from arq.connections import RedisSettings

    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.arq_redis_url))
        try:
            await pool.enqueue_job(
                "decide_conversation_task",
                conversation_id,
                _job_id=f"decide-{conversation_id}",
                _defer_by=delay_seconds,
            )
        finally:
            await pool.aclose()
    except Exception as exc:  # noqa: BLE001 - shadow mode must never break a message
        log.warning(
            "decisions.enqueue_failed conversation_id=%s err=%s", conversation_id, type(exc).__name__
        )


# ---------------------------------------------------------------------------
# People's answers
# ---------------------------------------------------------------------------
async def _human_answers(session: AsyncSession, conversation_ids: list[int]) -> dict[tuple[int, str], str]:
    if not conversation_ids:
        return {}
    rows = (
        await session.exec(
            select(HumanDecision).where(HumanDecision.conversation_id.in_(conversation_ids))  # type: ignore[attr-defined]
        )
    ).all()
    out = {(r.conversation_id, r.question): r.answer for r in rows}
    # The team an agent actually assigned is a human answer too.
    teams = (
        await session.exec(
            select(Conversation.id, Conversation.team_id).where(
                Conversation.id.in_(conversation_ids),  # type: ignore[union-attr]
                Conversation.team_id.is_not(None),  # type: ignore[union-attr]
            )
        )
    ).all()
    for conv_id, team_id in teams:
        out.setdefault((int(conv_id or 0), TEAM_QUESTION), f"team_{team_id}")
    return out


def _urgency_options(questions: list[dict[str, Any]]) -> set[str]:
    return {
        o["key"]
        for q in questions
        if q["key"] == URGENCY_QUESTION
        for o in q.get("options") or []
    }


async def next_to_label(
    session: AsyncSession, *, account_id: int, skip: list[int] | None = None
) -> dict[str, Any] | None:
    """A conversation the service decided and people have not labeled yet,
    with its text and the questions, never the service's answers."""
    questions = [
        q
        for q in await questions_for(session, account_id)
        if q.get("enabled") and len(q.get("options") or []) >= 2
    ]
    if not questions:
        return None
    keys = [q["key"] for q in questions]
    decided = (
        await session.exec(
            select(ConversationDecision.conversation_id, func.max(ConversationDecision.created_at))
            .where(ConversationDecision.account_id == account_id)
            .group_by(ConversationDecision.conversation_id)  # type: ignore[arg-type]
            .order_by(func.max(ConversationDecision.created_at).desc())
            .limit(200)
        )
    ).all()
    candidates = [int(r[0]) for r in decided]
    human = await _human_answers(session, candidates)
    for conv_id in candidates:
        conversation = await session.get(Conversation, conv_id)
        if conversation is None or (skip and conversation.display_id in skip):
            continue
        if all((conv_id, k) in human for k in keys):
            continue
        text, _ = await conversation_text(session, conversation, anonymized=False)
        if not text:
            continue
        return {
            "conversation_id": conversation.display_id,
            "text": text,
            "questions": questions,
            "answered": {k: human[(conv_id, k)] for k in keys if (conv_id, k) in human},
        }
    return None


async def save_labels(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int,
    conversation: Conversation,
    answers: dict[str, str],
) -> int:
    """Keep what a person says, question by question. Raises ValueError
    (``question`` / ``option``) for anything the account does not ask."""
    questions = {q["key"]: q for q in await questions_for(session, account_id)}
    saved = 0
    for key, answer in answers.items():
        q = questions.get(key)
        if q is None:
            raise ValueError("question")
        if answer not in {o["key"] for o in q.get("options") or []}:
            raise ValueError("option")
        row = (
            await session.exec(
                select(HumanDecision).where(
                    HumanDecision.conversation_id == conversation.id,
                    HumanDecision.question == key,
                )
            )
        ).first()
        if row is None:
            row = HumanDecision(
                account_id=account_id,
                conversation_id=conversation.id,
                question=key,
                answer=answer,
                user_id=user_id,
            )
        else:
            row.answer = answer
            row.user_id = user_id
        session.add(row)
        saved += 1
    await session.flush()
    return saved


# ---------------------------------------------------------------------------
# How it is doing
# ---------------------------------------------------------------------------
async def report(session: AsyncSession, *, account_id: int, days: int = 30) -> dict[str, Any]:
    """Per question: how many conversations it decided, how often it agrees
    with people where both answered, and how sure it was. Plus its cost."""
    since = _now() - timedelta(days=days)
    rows = (
        await session.exec(
            select(ConversationDecision)
            .where(
                ConversationDecision.account_id == account_id,
                ConversationDecision.created_at >= since,
            )
            .order_by(ConversationDecision.created_at)  # type: ignore[arg-type]
        )
    ).all()
    # The latest answer per conversation and question.
    latest: dict[tuple[int, str], ConversationDecision] = {}
    for r in rows:
        latest[(r.conversation_id, r.question)] = r
    account_questions = await questions_for(session, account_id)
    human = await _human_answers(session, sorted({c for c, _ in latest}))

    out_questions = []
    for q in account_questions:
        decided = [d for (c, k), d in latest.items() if k == q["key"]]
        compared = [(d, human[(d.conversation_id, q["key"])]) for d in decided if (d.conversation_id, q["key"]) in human]
        agree = sum(1 for d, h in compared if d.answer == h)
        confidences = [d.confidence for d in decided if d.confidence is not None]
        counts: dict[str, int] = {}
        for d in decided:
            counts[d.answer] = counts.get(d.answer, 0) + 1
        out_questions.append(
            {
                "key": q["key"],
                "instructions": q["instructions"],
                "options": q["options"],
                "decided": len(decided),
                "compared": len(compared),
                "agreed": agree,
                "agreement": round(agree / len(compared), 3) if compared else None,
                "mean_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
                "answers": counts,
            }
        )

    month_start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cost_row = (
        await session.exec(
            select(func.count(), func.coalesce(func.sum(UsageRecord.cost), 0))
            .where(
                UsageRecord.account_id == account_id,
                UsageRecord.kind == KIND_AI,
                UsageRecord.category == USAGE_CATEGORY,
                UsageRecord.occurred_at >= month_start,
            )
        )
    ).one()
    labeled = (
        await session.exec(
            select(func.count(func.distinct(HumanDecision.conversation_id))).where(
                HumanDecision.account_id == account_id
            )
        )
    ).one()
    owners = (
        await session.exec(
            select(func.count(), func.count().filter(PriorityOwner.corrected.is_(True))).where(  # type: ignore[attr-defined]
                PriorityOwner.account_id == account_id,
                PriorityOwner.ai_level.is_not(None),  # type: ignore[union-attr]
            )
        )
    ).one()
    return {
        "days": days,
        "priority": {"set_by_ai": int(owners[0] or 0), "changed_by_others": int(owners[1] or 0)},
        "conversations": len({c for c, _ in latest}),
        "labeled_conversations": int(labeled or 0),
        "questions": out_questions,
        "month": {"calls": int(cost_row[0] or 0), "cost_usd": float(cost_row[1] or 0)},
    }


__all__ = [
    "PROVIDERS",
    "PROVIDER_API",
    "PROVIDER_LOCAL",
    "Prepared",
    "ask",
    "decide",
    "decide_delay",
    "enqueue_decide",
    "is_on",
    "newer_message",
    "next_to_label",
    "prepare",
    "present_settings",
    "priority_changed",
    "provider_ready",
    "questions_for",
    "report",
    "save_labels",
    "save_settings",
    "store",
]
