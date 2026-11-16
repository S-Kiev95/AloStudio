"""Decisions about conversations, in shadow mode (F10).

When a customer writes, the conversation is decided a little later (one job
per conversation, so a burst of messages is decided once). The decisions are
stored and measured against what people label without seeing them; nothing in
the conversation changes. The report compares both, per question.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.contacts.models import Contact
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.decisions import client
from app.domains.decisions.anonymize import anonymize
from app.domains.decisions.models import ConversationDecision, DecisionSettings, HumanDecision
from app.domains.decisions.questions import (
    TEAM_QUESTION,
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
# A burst of messages is decided once, this long after the first.
DECIDE_DELAY_SECONDS = 45
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


async def present_settings(session: AsyncSession, account_id: int) -> dict[str, Any]:
    row = await get_row(session, account_id)
    return {
        "enabled": bool(row and row.enabled),
        "configured": client.configured(),
        "model": get_settings().decisions_model,
        "questions": await questions_for(session, account_id, row),
    }


async def save_settings(
    session: AsyncSession, *, account_id: int, enabled: bool, questions: Any | None
) -> dict[str, Any]:
    """Raises ValueError (a short code) when the questions do not hold up."""
    row = await get_row(session, account_id)
    if row is None:
        row = DecisionSettings(account_id=account_id)
    row.enabled = enabled
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
    return bool(row and row.enabled) and client.configured()


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
    session: AsyncSession, conversation: Conversation, *, anonymized: bool = True
) -> tuple[str, int | None]:
    """The latest messages as one text, and the id of the newest. Anonymized
    for the service; as written for a person labeling."""
    messages = await _latest_messages(session, conversation.id)  # type: ignore[arg-type]
    if not messages:
        return "", None
    names = await _names(session, conversation) if anonymized else None
    text = _transcript(messages, names)
    # Keep the end (the newest messages) when it is too long.
    return text[-STATE_MAX_CHARS:], messages[-1].id


# ---------------------------------------------------------------------------
# Deciding
# ---------------------------------------------------------------------------
def _cost(model: str | None, input_tokens: int) -> Decimal | None:
    if model and model.startswith("jev"):
        return (Decimal(input_tokens) * JEV_USD_PER_MILLION_INPUT / Decimal(1_000_000)).quantize(
            Decimal("0.000001")
        )
    return Decimal("0")


async def decide(session: AsyncSession, conversation: Conversation) -> list[ConversationDecision]:
    """Ask the service about this conversation and keep its answers. Does
    nothing (and returns ``[]``) when the account has it off or nothing to ask.
    Raises :class:`client.DecisionsError` when the service fails."""
    account_id = conversation.account_id
    row = await get_row(session, account_id)
    if not (row and row.enabled) or not client.configured():
        return []
    asked = as_service_questions(await questions_for(session, account_id, row))
    if not asked:
        return []
    state, last_message_id = await conversation_text(session, conversation)
    if not state:
        return []
    result = await client.ask(state, asked)
    model = result.model or get_settings().decisions_model
    stored = [
        ConversationDecision(
            account_id=account_id,
            conversation_id=conversation.id,
            message_id=last_message_id,
            question=key,
            answer=answer.choice[:128],
            confidence=answer.confidence,
            probabilities=answer.probabilities or None,
            model=model,
        )
        for key, answer in result.answers.items()
        if key in asked
    ]
    for decision in stored:
        session.add(decision)
    session.add(
        UsageRecord(
            account_id=account_id,
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
    return stored


async def enqueue_decide(conversation_id: int) -> None:
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
                _defer_by=DECIDE_DELAY_SECONDS,
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
    human = await _human_answers(session, sorted({c for c, _ in latest}))

    out_questions = []
    for q in await questions_for(session, account_id):
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
    return {
        "days": days,
        "conversations": len({c for c, _ in latest}),
        "labeled_conversations": int(labeled or 0),
        "questions": out_questions,
        "month": {"calls": int(cost_row[0] or 0), "cost_usd": float(cost_row[1] or 0)},
    }


__all__ = [
    "decide",
    "enqueue_decide",
    "is_on",
    "next_to_label",
    "present_settings",
    "questions_for",
    "report",
    "save_labels",
    "save_settings",
]
