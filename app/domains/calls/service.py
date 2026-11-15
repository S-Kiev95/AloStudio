"""Calls (F7): the life of a call, whatever channel carries it.

The channel module (:mod:`app.domains.calls.whatsapp`) turns the provider's
events into these calls; the router lets an agent take a call, confirm it and
hang up. Every change reaches the agents of the inbox as a ``call.updated``
event carrying the whole call, so the panel shows it without asking again
(the request that created it may not have committed yet when the event
arrives).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.i18n import DEFAULT_LOCALE, t
from app.core.realtime import get_broadcaster
from app.domains.calls.models import (
    ACTIVE_STATUSES,
    CALL_COMPLETED,
    CALL_CONNECTING,
    CALL_FAILED,
    CALL_IN_PROGRESS,
    CALL_MISSED,
    CALL_RINGING,
    DIRECTION_INBOUND,
    DIRECTION_OUTBOUND,
    FINAL_STATUSES,
    Call,
    CallInboxSettings,
)
from app.domains.contacts.avatar import contact_thumbnail
from app.domains.contacts.models import Contact
from app.domains.conversations.models import (
    FILE_TYPE_AUDIO,
    Attachment,
    Conversation,
    Message,
)
from app.domains.conversations.permission import is_administrator
from app.domains.conversations.service import MessageBuilderParams, create_message
from app.domains.inboxes.models import Inbox, InboxMember
from app.domains.users.models import ACCOUNT_USER_ROLE_ADMINISTRATOR, AccountUser, User

log = logging.getLogger(__name__)

CALL_UPDATED = "call.updated"

# Meta gives about a minute to answer; past this a ringing call is over even
# if its end never reached us.
RINGING_TIMEOUT = timedelta(minutes=3)
# A call in progress whose end never arrived (the agent closed the browser,
# Meta's event got lost) is closed after this long.
IN_PROGRESS_TIMEOUT = timedelta(hours=6)
# How long Meta keeps a recording or transcript after announcing it.
MEDIA_RETENTION = timedelta(days=7)

# Our statuses in the message, with Chatwoot's names (``voice_call`` bubbles).
_MESSAGE_STATUS = {
    CALL_RINGING: "ringing",
    CALL_CONNECTING: "ringing",
    CALL_IN_PROGRESS: "in-progress",
    CALL_COMPLETED: "completed",
    CALL_MISSED: "no-answer",
    CALL_FAILED: "failed",
}


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Presenting
# ---------------------------------------------------------------------------
async def present_call(session: AsyncSession, call: Call) -> dict[str, Any]:
    """The call as the panel shows it (never the offer: that is fetched by
    the agent who answers)."""
    conversation = await session.get(Conversation, call.conversation_id)
    contact = await session.get(Contact, call.contact_id) if call.contact_id else None
    inbox = await session.get(Inbox, call.inbox_id)
    answered_by = (
        await session.get(User, call.answered_by_id) if call.answered_by_id else None
    )
    return {
        "id": call.id,
        "status": call.status,
        "direction": call.direction,
        "provider": call.provider,
        "inbox_id": call.inbox_id,
        "inbox_name": inbox.name if inbox is not None else None,
        "conversation_id": call.conversation_id,
        "conversation_display_id": conversation.display_id if conversation else None,
        "contact": (
            {
                "id": contact.id,
                "name": contact.name,
                "phone_number": contact.phone_number,
                "thumbnail": contact_thumbnail(contact),
            }
            if contact is not None
            else None
        ),
        "from_number": call.from_number,
        "answered_by": (
            {"id": answered_by.id, "name": answered_by.available_name or answered_by.name}
            if answered_by is not None
            else None
        ),
        "can_answer": (
            call.direction == DIRECTION_INBOUND
            and call.status == CALL_RINGING
            and bool(call.sdp_offer)
        ),
        "created_at": call.created_at,
        "answered_at": call.answered_at,
        "ended_at": call.ended_at,
        "duration_seconds": call.duration_seconds,
    }


def _message_data(call: Call, answered_by: User | None) -> dict[str, Any]:
    started = int(call.created_at.timestamp()) if call.created_at else int(_now().timestamp())
    return {
        "call_sid": call.provider_call_id,
        "call_id": call.id,
        "status": _MESSAGE_STATUS.get(call.status, call.status),
        "call_direction": call.direction,
        "provider": call.provider,
        "from_number": call.from_number,
        "to_number": call.to_number,
        "answered_by": (
            {"id": answered_by.id, "name": answered_by.available_name or answered_by.name}
            if answered_by is not None
            else None
        ),
        "duration": call.duration_seconds,
        "meta": {"created_at": started, "ringing_at": started},
        # "pending" while Meta prepares the file, "ready" once it is ours.
        "recording": _media_state(call, call.recording_requested, call.recording_attachment_id),
        "transcription": _media_state(call, call.transcription_requested, call.transcript),
        "transcript": call.transcript or None,
    }


def _media_state(call: Call, requested: bool, have: object) -> str | None:
    if have:
        return "ready"
    if requested and call.answered_at is not None and call.status != CALL_FAILED:
        return "pending"
    return None


# ---------------------------------------------------------------------------
# Who hears it
# ---------------------------------------------------------------------------
async def _agent_tokens(session: AsyncSession, *, account_id: int, inbox_id: int) -> list[str]:
    """Members of the inbox and administrators of the account: the people
    who see its conversations."""
    members = (
        await session.exec(
            select(User.pubsub_token)
            .join(InboxMember, InboxMember.user_id == User.id)  # type: ignore[arg-type]
            .where(InboxMember.inbox_id == inbox_id)
        )
    ).all()
    admins = (
        await session.exec(
            select(User.pubsub_token)
            .join(AccountUser, AccountUser.user_id == User.id)  # type: ignore[arg-type]
            .where(
                AccountUser.account_id == account_id,
                AccountUser.role == ACCOUNT_USER_ROLE_ADMINISTRATOR,
            )
        )
    ).all()
    return [token for token in {*members, *admins} if token]


async def broadcast_call(session: AsyncSession, call: Call) -> None:
    """Tell the inbox's agents. Best effort: a Redis hiccup must not lose
    the call, the panel also asks for the active calls every few seconds."""
    try:
        tokens = await _agent_tokens(session, account_id=call.account_id, inbox_id=call.inbox_id)
        if not tokens:
            return
        payload = {"call": await present_call(session, call), "account_id": call.account_id}
        broadcaster = await get_broadcaster()
        await broadcaster.publish(tokens, CALL_UPDATED, payload)
    except Exception:
        log.exception("calls.broadcast_failed call_id=%s", call.id)


async def can_see(session: AsyncSession, *, call: Call, account_id: int, user_id: int) -> bool:
    if call.account_id != account_id:
        return False
    if await is_administrator(session, account_id=account_id, user_id=user_id):
        return True
    member = (
        await session.exec(
            select(InboxMember.id).where(
                InboxMember.inbox_id == call.inbox_id, InboxMember.user_id == user_id
            )
        )
    ).first()
    return member is not None


async def active_calls(session: AsyncSession, *, account_id: int, user_id: int) -> list[Call]:
    """Calls ringing or under way in the inboxes this person works."""
    stmt = select(Call).where(
        Call.account_id == account_id,
        Call.status.in_(ACTIVE_STATUSES),  # type: ignore[attr-defined]
        Call.created_at > _now() - IN_PROGRESS_TIMEOUT,
    )
    if not await is_administrator(session, account_id=account_id, user_id=user_id):
        stmt = stmt.where(
            Call.inbox_id.in_(  # type: ignore[attr-defined]
                select(InboxMember.inbox_id).where(InboxMember.user_id == user_id)
            )
        )
    rows = (await session.exec(stmt.order_by(Call.created_at))).all()  # type: ignore[arg-type]
    return [call for call in rows if not _stale(call, _now())]


def _stale(call: Call, now: datetime) -> bool:
    """Over, though its end never reached us. A ringing call ages from when
    it started; one somebody took, from when they took it (answering can
    run past the ringing time, and must not vanish from their screen)."""
    if call.status == CALL_RINGING:
        return call.created_at < now - RINGING_TIMEOUT
    if call.status == CALL_CONNECTING:
        return call.updated_at < now - RINGING_TIMEOUT
    if call.status == CALL_IN_PROGRESS:
        return call.created_at < now - IN_PROGRESS_TIMEOUT
    return False


async def get_call(session: AsyncSession, *, account_id: int, call_id: int) -> Call | None:
    call = await session.get(Call, call_id)
    if call is None or call.account_id != account_id:
        return None
    return call


async def by_provider_id(session: AsyncSession, provider_call_id: str) -> Call | None:
    return (
        await session.exec(select(Call).where(Call.provider_call_id == provider_call_id))
    ).first()


# ---------------------------------------------------------------------------
# A call starts
# ---------------------------------------------------------------------------
async def start_inbound(
    session: AsyncSession,
    *,
    conversation: Conversation,
    contact: Contact,
    provider: str,
    provider_call_id: str,
    from_number: str | None,
    to_number: str | None,
    sdp_offer: str | None,
) -> Call | None:
    """Record a call the customer is making and put it in the conversation.
    ``None`` when Meta repeats an event we already have."""
    if await by_provider_id(session, provider_call_id) is not None:
        return None
    call = Call(
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        contact_id=contact.id,
        provider=provider,
        provider_call_id=provider_call_id,
        status=CALL_RINGING,
        from_number=from_number,
        to_number=to_number,
        sdp_offer=sdp_offer,
    )
    session.add(call)
    await session.flush()
    await session.refresh(call)
    message = await create_message(
        session,
        conversation=conversation,
        params=MessageBuilderParams(
            content=t(DEFAULT_LOCALE, "calls.message"),
            message_type="incoming",
            content_type="voice_call",
            content_attributes={"data": _message_data(call, None)},
            source_id=provider_call_id,
        ),
        user_id=None,
    )
    call.message_id = message.id
    session.add(call)
    await session.flush()
    await broadcast_call(session, call)
    log.info(
        "calls.started call_id=%s provider_call_id=%s conversation_id=%s",
        call.id,
        provider_call_id,
        conversation.id,
    )
    return call


async def _sync_message(session: AsyncSession, call: Call) -> None:
    """Keep the conversation's bubble in step with the call."""
    if call.message_id is None:
        return
    message = await session.get(Message, call.message_id)
    if message is None:
        return
    answered_by = (
        await session.get(User, call.answered_by_id) if call.answered_by_id else None
    )
    attrs = dict(message.content_attributes or {})
    attrs["data"] = _message_data(call, answered_by)
    message.content_attributes = attrs
    session.add(message)
    await session.flush()


async def _lock(session: AsyncSession, call: Call) -> None:
    """Hold the call's row and read it fresh. The agent's request and Meta's
    event can change the same call at once (hanging up while Meta reports
    the end, Meta ending it while the answer is confirmed); one waits for
    the other, then sees what it did."""
    await session.refresh(call, with_for_update=True)


# ---------------------------------------------------------------------------
# A call we make
# ---------------------------------------------------------------------------
async def start_outbound(
    session: AsyncSession,
    *,
    conversation: Conversation,
    contact: Contact,
    agent_id: int,
    provider: str,
    provider_call_id: str,
    from_number: str | None,
    to_number: str | None,
    record: bool = False,
    transcribe: bool = False,
) -> Call:
    """Record a call an agent placed and put it in the conversation. The
    agent is its ``answered_by`` from the start: it is their call."""
    call = Call(
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        contact_id=contact.id,
        provider=provider,
        provider_call_id=provider_call_id,
        direction=DIRECTION_OUTBOUND,
        status=CALL_RINGING,
        from_number=from_number,
        to_number=to_number,
        answered_by_id=agent_id,
        recording_requested=record,
        transcription_requested=transcribe,
    )
    session.add(call)
    await session.flush()
    await session.refresh(call)
    agent = await session.get(User, agent_id)
    message = await create_message(
        session,
        conversation=conversation,
        params=MessageBuilderParams(
            content=t(DEFAULT_LOCALE, "calls.message"),
            message_type="outgoing",
            content_type="voice_call",
            # Already "sent": the call itself went out through Meta. Without
            # this the WhatsApp sender would text the customer the bubble.
            content_attributes={"data": _message_data(call, agent), "external_echo": True},
            source_id=provider_call_id,
        ),
        user_id=agent_id,
    )
    call.message_id = message.id
    session.add(call)
    await session.flush()
    await broadcast_call(session, call)
    log.info(
        "calls.placed call_id=%s provider_call_id=%s conversation_id=%s",
        call.id,
        provider_call_id,
        conversation.id,
    )
    return call


async def save_answer(session: AsyncSession, *, call: Call, sdp: str) -> None:
    """The customer's side of the audio path, for the agent's browser."""
    await _lock(session, call)
    if call.direction != DIRECTION_OUTBOUND or call.status in FINAL_STATUSES:
        return
    call.sdp_answer = sdp
    session.add(call)
    await session.flush()
    await broadcast_call(session, call)


async def customer_answered(session: AsyncSession, *, call: Call) -> None:
    """The customer picked up a call we made."""
    await _lock(session, call)
    if call.direction != DIRECTION_OUTBOUND or call.status != CALL_RINGING:
        return
    call.status = CALL_IN_PROGRESS
    call.answered_at = _now()
    session.add(call)
    await session.flush()
    await _sync_message(session, call)
    await broadcast_call(session, call)


# ---------------------------------------------------------------------------
# An agent answers
# ---------------------------------------------------------------------------
async def claim(session: AsyncSession, *, call: Call, user_id: int) -> bool:
    """Take a ringing call for this agent. Exactly one agent wins: the
    update only matches while the call still rings (a second agent's
    update waits for the first to commit, then matches nothing)."""
    result = await session.exec(
        update(Call)  # type: ignore[call-overload]
        .where(
            Call.id == call.id,  # type: ignore[arg-type]
            Call.status == CALL_RINGING,  # type: ignore[arg-type]
            Call.direction == DIRECTION_INBOUND,  # type: ignore[arg-type]
        )
        .values(status=CALL_CONNECTING, answered_by_id=user_id, updated_at=_now())
        .returning(Call.id)
    )
    won = result.first() is not None
    await session.refresh(call)
    if won:
        await _sync_message(session, call)
        await broadcast_call(session, call)
    return won


async def release(session: AsyncSession, *, call: Call) -> None:
    """Give a call back to the others when taking it failed before Meta
    heard of it."""
    await _lock(session, call)
    if call.status != CALL_CONNECTING:
        return
    call.status = CALL_RINGING
    call.answered_by_id = None
    session.add(call)
    await session.flush()
    await _sync_message(session, call)
    await broadcast_call(session, call)


async def mark_in_progress(
    session: AsyncSession, *, call: Call, record: bool = False, transcribe: bool = False
) -> None:
    """Meta confirmed the answer (recording / transcribing it if we asked).
    Unless the call ended meanwhile."""
    await _lock(session, call)
    if call.status != CALL_CONNECTING:
        return
    call.recording_requested = record
    call.transcription_requested = transcribe
    call.status = CALL_IN_PROGRESS
    call.answered_at = _now()
    session.add(call)
    await session.flush()
    await _sync_message(session, call)
    await broadcast_call(session, call)


# ---------------------------------------------------------------------------
# Recording and transcription
# ---------------------------------------------------------------------------
def recording_allowed() -> bool:
    """The installation's operator decides whether calls may be recorded."""
    return bool(get_settings().call_recording_allowed)


async def inbox_settings(session: AsyncSession, inbox_id: int) -> CallInboxSettings | None:
    return await session.get(CallInboxSettings, inbox_id)


async def recording_plan(session: AsyncSession, call: Call) -> CallInboxSettings | None:
    """What to ask Meta for when this call is answered: the inbox's choice,
    only while the installation allows recording."""
    return await recording_plan_for_inbox(session, call.inbox_id)


async def recording_plan_for_inbox(
    session: AsyncSession, inbox_id: int
) -> CallInboxSettings | None:
    if not recording_allowed():
        return None
    plan = await inbox_settings(session, inbox_id)
    if plan is None or not (plan.record or plan.transcribe):
        return None
    return plan


def default_purpose() -> str:
    return t(DEFAULT_LOCALE, "calls.default_purpose")


def default_permission_text() -> str:
    """What the customer reads above WhatsApp's own allow/deny buttons."""
    return t(DEFAULT_LOCALE, "calls.permission.request")


async def media_announced(
    session: AsyncSession, *, call: Call, kind: str, media_id: str
) -> None:
    """Meta has the recording or transcript ready; keep its id until we have
    our copy (Meta deletes it after 7 days)."""
    await _lock(session, call)
    if kind == "recording":
        if call.recording_attachment_id is not None:
            return
        call.recording_media_id = media_id
        call.recording_available_at = _now()
    else:
        if call.transcript:
            return
        call.transcript_media_id = media_id
        call.transcript_available_at = _now()
    session.add(call)
    await session.flush()


async def attach_recording(
    session: AsyncSession, *, call: Call, external_url: str, extension: str | None
) -> None:
    """Hang our copy of the audio off the call's message: it plays in the
    conversation, behind the same access rules as any attachment."""
    await _lock(session, call)
    if call.recording_attachment_id is not None or call.message_id is None:
        return
    ext = (extension or "ogg").lstrip(".")
    attachment = Attachment(
        account_id=call.account_id,
        message_id=call.message_id,
        file_type=FILE_TYPE_AUDIO,
        external_url=external_url,
        extension=ext,
        fallback_title=f"llamada-{call.id}.{ext}",
        coordinates_lat=0.0,
        coordinates_long=0.0,
    )
    session.add(attachment)
    await session.flush()
    call.recording_attachment_id = attachment.id
    call.recording_media_id = None
    session.add(call)
    await session.flush()
    await _sync_message(session, call)
    await broadcast_call(session, call)


async def save_transcript(
    session: AsyncSession,
    *,
    call: Call,
    segments: list[dict[str, Any]],
    language: str | None,
) -> None:
    """Keep what was said, in the call and as the message's text: search
    finds a call by its words, and the meaning index picks it up again."""
    await _lock(session, call)
    if call.transcript:
        return
    call.transcript = segments
    call.transcript_language = (language or "")[:16] or None
    call.transcript_media_id = None
    session.add(call)
    await session.flush()
    if call.message_id is not None:
        message = await session.get(Message, call.message_id)
        if message is not None:
            labels = {
                "business": t(DEFAULT_LOCALE, "calls.speaker.business"),
                "customer": t(DEFAULT_LOCALE, "calls.speaker.customer"),
            }
            lines = [f"{labels.get(s['speaker'], s['speaker'])}: {s['text']}" for s in segments]
            text = t(DEFAULT_LOCALE, "calls.message")
            if lines:
                text = text + "\n\n" + "\n".join(lines)
            message.content = text[:150_000]
            message.processed_message_content = message.content
            session.add(message)
            await session.flush()
            # The vector of "Llamada de WhatsApp" says nothing; drop it so the
            # meaning index embeds what was said instead.
            from app.domains.conversations.message_embeddings import MessageEmbedding

            existing = await session.get(MessageEmbedding, message.id)
            if existing is not None:
                await session.delete(existing)
                await session.flush()
    await _sync_message(session, call)
    await broadcast_call(session, call)


async def pending_media(session: AsyncSession) -> list[Call]:
    """Calls whose recording or transcript Meta announced and we have not
    copied yet, still inside Meta's 7 days."""
    since = _now() - MEDIA_RETENTION
    rows = (
        await session.exec(
            select(Call).where(
                (
                    Call.recording_media_id.is_not(None)  # type: ignore[union-attr]
                    & (Call.recording_available_at > since)  # type: ignore[operator]
                )
                | (
                    Call.transcript_media_id.is_not(None)  # type: ignore[union-attr]
                    & (Call.transcript_available_at > since)  # type: ignore[operator]
                )
            )
        )
    ).all()
    return list(rows)


# ---------------------------------------------------------------------------
# A call ends
# ---------------------------------------------------------------------------
async def finish(
    session: AsyncSession,
    *,
    call: Call,
    status: str,
    ended_at: datetime | None = None,
    duration_seconds: int | None = None,
    reason: str | None = None,
) -> None:
    """Close the call. Meta's end event can arrive after we closed it
    ourselves (the agent hung up): it then only brings the exact length."""
    await _lock(session, call)
    already_over = call.status in FINAL_STATUSES
    if not already_over:
        call.status = status
    call.ended_at = ended_at or call.ended_at or _now()
    if duration_seconds is not None:
        call.duration_seconds = duration_seconds
    elif call.duration_seconds is None and call.answered_at is not None:
        call.duration_seconds = max(0, int((call.ended_at - call.answered_at).total_seconds()))
    if reason and not call.end_reason:
        call.end_reason = reason[:500]
    call.sdp_offer = None
    session.add(call)
    await session.flush()
    await _sync_message(session, call)
    await broadcast_call(session, call)
    if not already_over:
        log.info(
            "calls.finished call_id=%s status=%s duration=%s",
            call.id,
            call.status,
            call.duration_seconds,
        )


async def expire_stale(session: AsyncSession) -> int:
    """Close calls whose end never reached us. Run by the 5-minute tick."""
    now = _now()
    rows = (
        await session.exec(
            select(Call).where(
                Call.status.in_(ACTIVE_STATUSES),  # type: ignore[attr-defined]
                Call.created_at < now - RINGING_TIMEOUT,
            )
        )
    ).all()
    closed = 0
    for call in rows:
        if not _stale(call, now):
            continue
        if call.status == CALL_RINGING:
            await finish(session, call=call, status=CALL_MISSED)
        elif call.status == CALL_CONNECTING:
            await finish(session, call=call, status=CALL_FAILED, reason="no_confirmation")
        else:
            await finish(session, call=call, status=CALL_COMPLETED)
        closed += 1
    return closed


__all__ = [
    "CALL_UPDATED",
    "active_calls",
    "broadcast_call",
    "by_provider_id",
    "can_see",
    "claim",
    "customer_answered",
    "expire_stale",
    "finish",
    "get_call",
    "mark_in_progress",
    "present_call",
    "release",
    "save_answer",
    "start_inbound",
    "start_outbound",
]
