"""The voice AI that answers WhatsApp calls (F7 paso 3).

Each WhatsApp inbox says who answers its calls (``CallInboxSettings.ai_mode``):
its people (``off``, the default), or AloStudio's voice AI always, outside
the inbox's hours, or when nobody picked up in ``AI_NO_ANSWER_SECONDS``.
The AI never takes a call whose conversation is in a person's hands (open,
and somebody of the team wrote to the customer in the last day, or the AI
handed it over).

How a call reaches the AI:

1. Meta's ``connect`` webhook records the call (:func:`on_ringing`). With
   ``always`` / ``after_hours`` the AI takes it right there, so it never
   rings in the panel; with ``no_answer`` it rings as usual.
2. A worker task (:func:`voice_answer_call_task`, deferred a second, or
   ``AI_NO_ANSWER_SECONDS``) hands Meta's WebRTC offer and the AI's
   instructions to the voice process (``python -m app.voice``, Pipecat and
   Gemini Live). It answers with its SDP, which goes to Meta in the same two
   steps an agent's browser uses (``pre_accept``, ``accept``).
3. The audio flows between Meta and the voice process. Its tools call back
   into this module: :func:`ai_handoff` (the customer wants a person: the
   same handoff Meta Business Agent does, with its notice) and
   :func:`ai_hangup`; at the end :func:`ai_call_over` keeps what was said
   and what it cost.

Anything failing before Meta heard our answer gives the call back to the
people of the inbox (:func:`calls.release`): the customer only hears it ring
a little longer.

The AI always opens saying it is an AI and that what it says is not binding
(``calls.ai.disclaimer``), whatever greeting the admin wrote.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.calls import service as calls
from app.domains.calls.models import (
    AI_MODE_AFTER_HOURS,
    AI_MODE_ALWAYS,
    AI_MODE_NO_ANSWER,
    AI_MODE_OFF,
    AI_NO_ANSWER_SECONDS,
    AI_VOICES,
    CALL_COMPLETED,
    CALL_CONNECTING,
    CALL_FAILED,
    CALL_IN_PROGRESS,
    CALL_RINGING,
    DIRECTION_INBOUND,
    FINAL_STATUSES,
    Call,
    CallInboxSettings,
)
from app.domains.conversations.models import CONVERSATION_STATUS_OPEN, Conversation

log = logging.getLogger(__name__)

TASK_NAME = "voice_answer_call_task"
# Long enough for the webhook that recorded the call to commit.
_IMMEDIATE_DELAY = timedelta(seconds=1)
_SERVICE_TIMEOUT = 15.0
# What the AI may read about the business: whole Help Center articles and
# products, up to these sizes (Gemini Live keeps it all in context).
_ARTICLES_MAX_CHARS = 30_000
_PRODUCTS_MAX = 100
USAGE_PURPOSE = "voice_call"
# A person who wrote to the customer this recently is on the conversation.
HUMAN_REPLY_WINDOW = timedelta(hours=24)
# Gemini Live list prices, USD per 1M tokens (text in, audio in, text out,
# audio out), read on 2026-11-25 at https://aistudio.google.com/docs/pricing.
_PRICES: dict[str, tuple[Decimal, Decimal, Decimal, Decimal]] = {
    "gemini-3.8-live": (Decimal("0.75"), Decimal("3.00"), Decimal("4.50"), Decimal("12.00")),
    "gemini-3.1-flash-live-preview": (
        Decimal("0.75"),
        Decimal("3.00"),
        Decimal("4.50"),
        Decimal("12.00"),
    ),
}


def ready() -> bool:
    """The installation has a Gemini key and a voice process to talk to."""
    settings = get_settings()
    return bool(
        settings.gemini_api_key and settings.voice_service_url and settings.voice_service_token
    )


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Who answers
# ---------------------------------------------------------------------------
async def human_owns(session: AsyncSession, conversation: Conversation) -> bool:
    """A person is on this open conversation: the AI handed it over, or
    somebody of the team wrote to the customer in the last
    ``HUMAN_REPLY_WINDOW``. Having an assignee is not enough: automatic
    assignment gives every new conversation one."""
    from app.domains.conversations.models import MESSAGE_TYPE_OUTGOING, Message

    if conversation.status != CONVERSATION_STATUS_OPEN:
        return False
    labels = [x.strip() for x in (conversation.cached_label_list or "").split(",")]
    if t(DEFAULT_LOCALE, "calls.ai.label") in labels:
        return True
    replied = (
        await session.exec(
            select(Message.id)
            .where(
                Message.conversation_id == conversation.id,
                Message.message_type == MESSAGE_TYPE_OUTGOING,
                Message.private == False,  # noqa: E712
                Message.sender_type == "User",
                Message.created_at > _now() - HUMAN_REPLY_WINDOW,
            )
            .limit(1)
        )
    ).first()
    return replied is not None


async def _inside_hours(session: AsyncSession, inbox_id: int, now: datetime) -> bool:
    """Whether the inbox is open now. An inbox without hours is always open."""
    from app.domains.inboxes.models import Inbox
    from app.domains.working_hours.service import business_hours_between, list_for_inbox

    inbox = await session.get(Inbox, inbox_id)
    if inbox is None or not inbox.working_hours_enabled:
        return True
    rows = await list_for_inbox(session, inbox_id=inbox_id)
    if not rows:
        return True
    return (
        business_hours_between(
            rows=rows, timezone_name=inbox.timezone, start=now, end=now + timedelta(minutes=1)
        )
        > 0
    )


async def _wants_ai(session: AsyncSession, call: Call, row: CallInboxSettings | None) -> bool:
    """The inbox wants the AI on this call right now (the mode aside from
    ``no_answer``'s wait), and the conversation is not a person's."""
    if row is None or row.ai_mode == AI_MODE_OFF or not ready():
        return False
    if call.direction != DIRECTION_INBOUND or not call.sdp_offer:
        return False
    if row.ai_mode == AI_MODE_AFTER_HOURS and await _inside_hours(session, call.inbox_id, _now()):
        return False
    conversation = await session.get(Conversation, call.conversation_id)
    if conversation is None or await human_owns(session, conversation):
        return False
    from app.domains.usage.limits import limit_reached
    from app.domains.usage.models import KIND_AI

    return not await limit_reached(session, call.account_id, KIND_AI)


async def on_ringing(session: AsyncSession, call: Call) -> None:
    """A customer's call was just recorded: decide whether the AI takes it.
    Never raises: the call must still ring if anything here fails."""
    try:
        row = await calls.inbox_settings(session, call.inbox_id)
        if not await _wants_ai(session, call, row):
            return
        assert row is not None
        if row.ai_mode in (AI_MODE_ALWAYS, AI_MODE_AFTER_HOURS):
            if not await calls.claim_for_ai(session, call=call):
                return
            await enqueue_answer(call_id=int(call.id or 0), delay=_IMMEDIATE_DELAY)
        elif row.ai_mode == AI_MODE_NO_ANSWER:
            await enqueue_answer(
                call_id=int(call.id or 0), delay=timedelta(seconds=AI_NO_ANSWER_SECONDS)
            )
    except Exception:
        log.exception("calls.voice.on_ringing_failed call_id=%s", call.id)


async def enqueue_answer(*, call_id: int, delay: timedelta) -> None:
    """Queue the AI's answer. With no worker the call stays with the people
    (a call taken for the AI is given back by the task, or by the tick)."""
    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(get_settings().arq_redis_url))
    try:
        await pool.enqueue_job(TASK_NAME, call_id, _defer_by=delay)
    finally:
        await pool.aclose()


async def voice_answer_call_task(ctx: dict[str, Any], call_id: int) -> dict[str, Any]:
    """ARQ task: answer the call with the voice AI, in the task's own session."""
    from app.core.db import get_session_factory

    engine = ctx.get("engine") if isinstance(ctx, dict) else None
    factory = (
        async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )
        if engine is not None
        else get_session_factory()
    )
    async with factory() as session:
        try:
            outcome = await answer_with_ai(session, call_id=call_id)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("calls.voice.answer_crashed call_id=%s", call_id)
            outcome = "error"
    log.info("calls.voice.answer call_id=%s outcome=%s", call_id, outcome)
    return {"call_id": call_id, "outcome": outcome}


# ---------------------------------------------------------------------------
# Answering
# ---------------------------------------------------------------------------
async def answer_with_ai(session: AsyncSession, *, call_id: int) -> str:
    """Hand the call to the voice process and answer Meta with its SDP.
    Returns what happened, for the log."""
    from app.domains.calls import whatsapp

    call = await session.get(Call, call_id)
    if call is None:
        return "gone"
    if call.status == CALL_RINGING:
        # ``no_answer``: nobody took it in the wait. Ask again, things changed.
        row = await calls.inbox_settings(session, call.inbox_id)
        if not await _wants_ai(session, call, row):
            return "not_wanted"
        if not await calls.claim_for_ai(session, call=call):
            return "taken"
    if call.status != CALL_CONNECTING or not call.ai_answered:
        return "taken" if call.status not in FINAL_STATUSES else "over"
    row = await calls.inbox_settings(session, call.inbox_id)
    offer = call.sdp_offer
    if row is None or not offer or not ready():
        await calls.release(session, call=call)
        return "not_ready"
    spec = {
        "call_id": call.id,
        "provider_call_id": call.provider_call_id,
        "account_id": call.account_id,
        "sdp_offer": offer,
        "instructions": await build_instructions(session, call, row),
        "voice": row.ai_voice if row.ai_voice in AI_VOICES else AI_VOICES[0],
        "model": get_settings().voice_ai_model,
    }
    try:
        answer = await _service("POST", "/calls", json=spec)
        sdp = str(answer.get("sdp_answer") or "")
        if not sdp:
            raise VoiceError("no sdp_answer")
    except VoiceError as exc:
        log.warning("calls.voice.service_failed call_id=%s error=%s", call.id, exc)
        await calls.release(session, call=call)
        return "service_failed"
    try:
        await whatsapp.pre_accept(session, call=call, sdp=sdp)
    except whatsapp.CallError as exc:
        log.warning("calls.voice.pre_accept_failed call_id=%s error=%s", call.id, exc.code)
        await end_ai_call(call.provider_call_id)
        await calls.release(session, call=call)
        return "pre_accept_failed"
    plan = await calls.recording_plan(session, call)
    try:
        await whatsapp.accept(session, call=call, sdp=sdp, plan=plan)
    except whatsapp.CallError as exc:
        # Meta has our answer: nobody else can take it. Hang up rather than
        # leave the customer on silence, as an agent's failed accept does.
        with contextlib.suppress(whatsapp.CallError):
            await whatsapp.terminate(session, call=call)
        await end_ai_call(call.provider_call_id)
        await calls.finish(session, call=call, status=CALL_FAILED, reason=exc.detail or exc.code)
        return "accept_failed"
    await calls.mark_in_progress(
        session,
        call=call,
        record=bool(plan and plan.record),
        transcribe=bool(plan and plan.transcribe),
    )
    return "answered"


class VoiceError(Exception):
    pass


async def _service(method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = get_settings()
    url = settings.voice_service_url.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=_SERVICE_TIMEOUT) as client:
            response = await client.request(
                method,
                url,
                json=json,
                headers={"Authorization": f"Bearer {settings.voice_service_token}"},
            )
    except httpx.HTTPError as exc:
        raise VoiceError(type(exc).__name__) from exc
    if response.status_code >= 400:
        raise VoiceError(f"http {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


async def end_ai_call(provider_call_id: str) -> None:
    """Tell the voice process to drop a call. Best effort."""
    if not ready():
        return
    try:
        await _service("POST", f"/calls/{provider_call_id}/end")
    except VoiceError as exc:
        log.info("calls.voice.end_failed provider_call_id=%s error=%s", provider_call_id, exc)


# ---------------------------------------------------------------------------
# What the AI knows
# ---------------------------------------------------------------------------
def opening_line(business: str, row: CallInboxSettings) -> str:
    """What the AI says first: the admin's greeting (or ours) and always
    that it is an AI and that what it says is not binding."""
    greeting = (row.ai_greeting or "").strip() or t(
        DEFAULT_LOCALE, "calls.ai.greeting", business=business
    )
    return f"{greeting} {t(DEFAULT_LOCALE, 'calls.ai.disclaimer')}"


async def _business_name(session: AsyncSession, account_id: int) -> str:
    from app.domains.accounts.models import Account

    account = await session.get(Account, account_id)
    return account.name if account is not None else ""


async def _articles(session: AsyncSession, account_id: int) -> str:
    from app.domains.portals.models import ARTICLE_STATUS_PUBLISHED, Article

    rows = (
        await session.exec(
            select(Article)
            .where(Article.account_id == account_id, Article.status == ARTICLE_STATUS_PUBLISHED)
            .order_by(Article.views.desc(), Article.id.desc())  # type: ignore[attr-defined]
            .limit(200)
        )
    ).all()
    parts: list[str] = []
    used = 0
    for article in rows:
        text = f"### {article.title or ''}\n{(article.content or '').strip()}\n"
        if used + len(text) > _ARTICLES_MAX_CHARS:
            break
        parts.append(text)
        used += len(text)
    return "\n".join(parts)


async def _products(session: AsyncSession, account_id: int) -> str:
    from app.domains.products.service import list_products

    rows = await list_products(session, account_id=account_id, enabled=True, per_page=_PRODUCTS_MAX)
    lines = []
    for product in rows:
        price = f" — {product.price} {product.currency or ''}".rstrip() if product.price else ""
        description = f": {product.description.strip()[:300]}" if product.description else ""
        lines.append(f"- {product.name}{price}{description}")
    return "\n".join(lines)


async def build_instructions(session: AsyncSession, call: Call, row: CallInboxSettings) -> str:
    """The AI's system instruction for this call."""
    from app.domains.contacts.models import Contact

    business = await _business_name(session, call.account_id)
    contact = await session.get(Contact, call.contact_id) if call.contact_id else None
    opening = opening_line(business, row)
    sections = [
        f"Sos el asistente de voz con inteligencia artificial de «{business}». "
        "Atendés una llamada de WhatsApp de un cliente.",
        "Reglas:\n"
        f"- Empezá diciendo exactamente: «{opening}»\n"
        "- Nunca digas que sos una persona. Si te preguntan, aclará que sos una IA y que lo "
        "que decís es orientativo y no es vinculante: precios, turnos, condiciones y "
        "cualquier compromiso los confirma una persona del equipo.\n"
        "- Hablá en español rioplatense, de vos, cálido y claro. Si el cliente habla otro "
        "idioma, respondé en el suyo.\n"
        "- Es una llamada: respuestas cortas, una idea por vez, sin listas ni símbolos.\n"
        "- Usá solo la información de abajo. Si algo no está, decí que no lo sabés y ofrecé "
        "que una persona lo contacte. No inventes precios, plazos, stock ni promesas.\n"
        "- Nunca pidas ni aceptes datos de tarjetas, contraseñas ni códigos.\n"
        "- Si el cliente pide hablar con una persona, o el tema lo necesita (un reclamo, un "
        "pago, algo que no podés resolver), usá la herramienta derivar_a_persona con el "
        "motivo y un resumen de lo hablado, y decile que una persona del equipo lo va a "
        "contactar por este mismo WhatsApp lo antes posible.\n"
        "- Cuando el cliente se despide o ya no hay nada más, despedite en una frase y usá "
        "la herramienta terminar_llamada.",
    ]
    if contact is not None and contact.name:
        sections.append(f"El cliente se llama {contact.name} (según WhatsApp).")
    if row.ai_instructions and row.ai_instructions.strip():
        sections.append("Lo que el negocio quiere que sepas:\n" + row.ai_instructions.strip())
    articles = await _articles(session, call.account_id)
    if articles:
        sections.append("Centro de ayuda del negocio:\n" + articles)
    products = await _products(session, call.account_id)
    if products:
        sections.append("Productos y servicios:\n" + products)
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Called by the voice process during and after the call
# ---------------------------------------------------------------------------
async def ai_handoff(
    session: AsyncSession, *, provider_call_id: str, reason: str, summary: str
) -> bool:
    """The customer wants a person: leave the AI's summary as a private
    note, mark the conversation and hand it over the way Meta Business
    Agent's handoffs do (``bot_handoff``: open, the inbox's handoff
    assignee, the notice by panel, email, push or WhatsApp)."""
    from app.domains.conversations.service import (
        MessageBuilderParams,
        bot_handoff,
        create_message,
        update_labels,
    )

    call = await calls.by_provider_id(session, provider_call_id)
    if call is None or not call.ai_answered:
        return False
    conversation = await session.get(Conversation, call.conversation_id)
    if conversation is None:
        return False
    await create_message(
        session,
        conversation=conversation,
        params=MessageBuilderParams(
            content=t(
                DEFAULT_LOCALE,
                "calls.ai.handoff_note",
                reason=(reason or "-").strip()[:500],
                summary=(summary or "-").strip()[:3000],
            ),
            message_type="outgoing",
            private=True,
        ),
        user_id=None,
    )
    label = t(DEFAULT_LOCALE, "calls.ai.label")
    titles = [x.strip() for x in (conversation.cached_label_list or "").split(",") if x.strip()]
    if label not in titles:
        await update_labels(session, conversation=conversation, titles=[*titles, label])
    await bot_handoff(session, conversation=conversation)
    log.info("calls.voice.handoff call_id=%s conversation_id=%s", call.id, conversation.id)
    return True


async def ai_hangup(session: AsyncSession, *, provider_call_id: str) -> bool:
    """The AI said goodbye: end the call at Meta (its ``terminate`` event
    then closes it here, with the exact length)."""
    from app.domains.calls import whatsapp

    call = await calls.by_provider_id(session, provider_call_id)
    if call is None or not call.ai_answered or call.status in FINAL_STATUSES:
        return False
    try:
        await whatsapp.terminate(session, call=call)
    except whatsapp.CallError as exc:
        log.info("calls.voice.hangup_failed call_id=%s error=%s", call.id, exc.code)
    if call.status == CALL_IN_PROGRESS:
        await calls.finish(session, call=call, status=CALL_COMPLETED)
    return True


def cost_of(model: str, usage: dict[str, int]) -> Decimal | None:
    name = model.removeprefix("models/")
    prices = _PRICES.get(name)
    if prices is None:
        return None
    text_in, audio_in, text_out, audio_out = prices
    a_in = usage.get("input_audio_tokens", 0)
    a_out = usage.get("output_audio_tokens", 0)
    t_in = max(usage.get("input_tokens", 0) - a_in, 0)
    t_out = max(usage.get("output_tokens", 0) - a_out, 0)
    total = t_in * text_in + a_in * audio_in + t_out * text_out + a_out * audio_out
    return (total / Decimal(1_000_000)).quantize(Decimal("0.000001"))


async def ai_call_over(
    session: AsyncSession,
    *,
    provider_call_id: str,
    model: str,
    usage: dict[str, int],
    segments: list[dict[str, Any]],
) -> None:
    """The voice process finished a call: what it cost goes to the
    account's AI spend, and what was said becomes the call's transcript
    when Meta is not transcribing it."""
    from app.domains.usage.models import KIND_AI, UsageRecord

    call = await calls.by_provider_id(session, provider_call_id)
    if call is None:
        return
    if any(usage.values()):
        session.add(
            UsageRecord(
                account_id=call.account_id,
                kind=KIND_AI,
                occurred_at=_now(),
                category=USAGE_PURPOSE,
                model=model.removeprefix("models/"),
                input_tokens=int(usage.get("input_tokens", 0)),
                cached_tokens=int(usage.get("cached_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
                cost=cost_of(model, usage),
            )
        )
        await session.flush()
    if segments and not call.transcription_requested and not call.transcript:
        await calls.save_transcript(session, call=call, segments=segments, language=None)
