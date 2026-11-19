"""Call endpoints (F7).

Route map, under ``/api/v1/accounts/{account_id}/calls``:
  * ``GET  /active``                 — calls ringing or under way in my inboxes
  * ``GET  /settings/{inbox_id}``    — admin: the number's call settings on Meta
  * ``PUT  /settings/{inbox_id}``    — admin: turn calls on or off, hours, …
  * ``GET  /{id}``                   — one call; while it rings, with the
    caller's offer (``sdp_offer``) for the browser that answers
  * ``POST /{id}/pre_accept``        — ``{sdp}``: take the call (one agent
    wins, the rest get 409) and open the audio path
  * ``POST /{id}/accept``            — ``{sdp}`` (the same answer): start it
  * ``POST /{id}/hangup``            — end it
  * ``GET  /permission?conversation_id=`` — may the business call this
    customer (Meta keeps it): ``status``, ``can_call``, ``can_request``
  * ``POST /permission_request``     — ``{conversation_id, text?}``: ask them
    in the chat
  * ``POST /``                       — ``{conversation_id, sdp}``: call them
    with the browser's offer; the answer comes back as ``sdp_answer``

``conversation_id`` is the number the panel shows (``display_id``).

Errors carry ``code`` (``calls.taken``, ``calls.over``, ``calls.not_yours``,
``calls.not_connected``, ``calls.unreachable``, ``calls.refused``,
``calls.no_hours``, ``calls.recording_not_allowed``, ``calls.purpose``,
``calls.language``) for the panel to translate; ``message`` is Meta's reason
when it gave one.

Recording and transcription (settings ``record`` / ``transcribe``) only
apply while the installation's operator allows it (``recording_allowed``).
"""

from __future__ import annotations

import contextlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.calls import service as calls
from app.domains.calls import whatsapp
from app.domains.calls.models import (
    ANNOUNCEMENT_LANGUAGES,
    CALL_COMPLETED,
    CALL_CONNECTING,
    CALL_FAILED,
    CALL_IN_PROGRESS,
    CALL_MISSED,
    CALL_RINGING,
    DIRECTION_OUTBOUND,
    FINAL_STATUSES,
    MISSED_TEXT_MAX,
    PURPOSE_MAX,
    Call,
    CallInboxSettings,
)
from app.domains.contacts.models import Contact
from app.domains.inboxes.models import CHANNEL_TYPE_WHATSAPP, Inbox, WhatsappChannel

router = APIRouter(prefix="/api/v1/accounts/{account_id}/calls", tags=["calls"])

# Refusals about the request or the customer (422), not about Meta failing.
_OUR_SIDE = ("not_connected", "no_hours", "no_phone", "no_permission", "limit", "window")

_NOT_FOUND = {"error": "Resource could not be found"}


class AnswerBody(BaseModel):
    # The browser's WebRTC answer; Meta wants the complete one (with the
    # candidates), not trickled.
    sdp: str = Field(min_length=10, max_length=20000)


class CallBody(BaseModel):
    conversation_id: int
    sdp: str = Field(min_length=10, max_length=20000)


class PermissionRequestBody(BaseModel):
    conversation_id: int
    text: str | None = Field(default=None, max_length=1024)


class SettingsBody(BaseModel):
    enabled: bool
    call_icon_visible: bool = True
    callback_requests: bool = True
    business_hours: bool = False
    # Recording (only while the installation allows it). Left out: unchanged.
    record: bool | None = None
    transcribe: bool | None = None
    purpose: str | None = None
    announcement_language: str | None = None
    # A call nobody answered. Left out: unchanged.
    missed_call_reply: bool | None = None
    missed_call_text: str | None = None


def _account_id(ctx: AccountContext) -> int:
    assert ctx.account.id is not None
    return ctx.account.id


def _user_id(ctx: AccountContext) -> int:
    assert ctx.user.id is not None
    return ctx.user.id


def _fail(status_code: int, code: str, message: str | None = None) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=status_code,
        detail={"message": message or code, "code": f"calls.{code}"},
    )


def _meta_fail(exc: whatsapp.CallError) -> ChatwootHTTPException:
    status = 422 if exc.code in _OUR_SIDE else 502
    return _fail(status, exc.code, exc.detail)


async def _visible_call(session: AsyncSession, ctx: AccountContext, call_id: int) -> Call:
    call = await calls.get_call(session, account_id=_account_id(ctx), call_id=call_id)
    if call is None or not await calls.can_see(
        session, call=call, account_id=_account_id(ctx), user_id=_user_id(ctx)
    ):
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    return call


async def _whatsapp_inbox(
    session: AsyncSession, ctx: AccountContext, inbox_id: int
) -> tuple[Inbox, WhatsappChannel]:
    inbox = await session.get(Inbox, inbox_id)
    if (
        inbox is None
        or inbox.account_id != _account_id(ctx)
        or inbox.channel_type != CHANNEL_TYPE_WHATSAPP
    ):
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    channel = await session.get(WhatsappChannel, inbox.channel_id)
    if channel is None:
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    return inbox, channel


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------
@router.get("/active")
async def index_active(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    rows = await calls.active_calls(
        session, account_id=_account_id(ctx), user_id=_user_id(ctx)
    )
    return {"payload": [await calls.present_call(session, c) for c in rows]}


# ---------------------------------------------------------------------------
# The number's settings
# ---------------------------------------------------------------------------
def _inbox_out(row: CallInboxSettings | None) -> dict[str, Any]:
    return {
        "recording_allowed": calls.recording_allowed(),
        "record": bool(row and row.record),
        "transcribe": bool(row and row.transcribe),
        "purpose": (row.purpose if row else None) or calls.default_purpose(),
        "announcement_language": (row.announcement_language if row else None) or "es",
        "missed_call_reply": row.missed_call_reply if row is not None else True,
        "missed_call_text": calls.missed_reply_text(row),
    }


async def _save_inbox(
    session: AsyncSession, *, inbox: Inbox, body: SettingsBody
) -> CallInboxSettings | None:
    """What the inbox does with its calls, ours to keep: recording (while the
    installation allows it) and what a customer nobody answered reads."""
    row = await calls.inbox_settings(session, inbox.id)  # type: ignore[arg-type]
    recording = any(
        value is not None
        for value in (body.record, body.transcribe, body.purpose, body.announcement_language)
    )
    missed = body.missed_call_reply is not None or body.missed_call_text is not None
    if not recording and not missed:
        return row
    if row is None:
        row = CallInboxSettings(inbox_id=inbox.id, account_id=inbox.account_id)
    if recording:
        _apply_recording(row, body)
    if body.missed_call_reply is not None:
        row.missed_call_reply = body.missed_call_reply
    if body.missed_call_text is not None:
        text = body.missed_call_text.strip()
        if len(text) > MISSED_TEXT_MAX:
            raise _fail(422, "missed_text")
        # Ours, or the default when it is ours word for word.
        row.missed_call_text = text if text and text != calls.missed_reply_text(None) else None
    session.add(row)
    await session.flush()
    return row


def _apply_recording(row: CallInboxSettings, body: SettingsBody) -> None:
    record = body.record if body.record is not None else row.record
    transcribe = body.transcribe if body.transcribe is not None else row.transcribe
    if (record or transcribe) and not calls.recording_allowed():
        raise _fail(422, "recording_not_allowed")
    purpose = (body.purpose if body.purpose is not None else row.purpose) or ""
    purpose = purpose.strip()
    if (record or transcribe) and not purpose:
        purpose = calls.default_purpose()
    if len(purpose) > PURPOSE_MAX:
        raise _fail(422, "purpose")
    language = body.announcement_language or row.announcement_language or "es"
    if language not in ANNOUNCEMENT_LANGUAGES:
        raise _fail(422, "language")
    row.record = record
    row.transcribe = transcribe
    row.purpose = purpose or None
    row.announcement_language = language


@router.get("/settings/{inbox_id}")
async def show_settings(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    _, channel = await _whatsapp_inbox(session, ctx, inbox_id)
    try:
        meta = await whatsapp.read_settings(channel)
    except whatsapp.CallError as exc:
        raise _meta_fail(exc) from exc
    return {**meta, **_inbox_out(await calls.inbox_settings(session, inbox_id))}


@router.put("/settings/{inbox_id}")
async def update_settings(
    inbox_id: Annotated[int, Path()],
    body: SettingsBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    inbox, channel = await _whatsapp_inbox(session, ctx, inbox_id)
    # Ours first: a refusal here must not leave Meta half changed.
    row = await _save_inbox(session, inbox=inbox, body=body)
    try:
        meta = await whatsapp.save_settings(
            session,
            channel=channel,
            inbox=inbox,
            enabled=body.enabled,
            call_icon_visible=body.call_icon_visible,
            callback_requests=body.callback_requests,
            business_hours=body.business_hours,
        )
    except whatsapp.CallError as exc:
        raise _meta_fail(exc) from exc
    return {**meta, **_inbox_out(row)}


# ---------------------------------------------------------------------------
# One call
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Calling a customer
# ---------------------------------------------------------------------------
async def _conversation_and_contact(
    session: AsyncSession, ctx: AccountContext, display_id: int
) -> tuple[Any, Contact]:
    from app.domains.conversations.router import _load_conversation_by_display_id

    conversation = await _load_conversation_by_display_id(session, ctx=ctx, display_id=display_id)
    contact = await session.get(Contact, conversation.contact_id) if conversation.contact_id else None
    if contact is None:
        raise _fail(422, "no_phone")
    return conversation, contact


@router.get("/permission")
async def show_permission(
    conversation_id: int,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    conversation, contact = await _conversation_and_contact(session, ctx, conversation_id)
    try:
        return await whatsapp.permission_state(session, conversation=conversation, contact=contact)
    except whatsapp.CallError as exc:
        raise _meta_fail(exc) from exc


@router.post("/permission_request")
async def create_permission_request(
    body: PermissionRequestBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    conversation, contact = await _conversation_and_contact(session, ctx, body.conversation_id)
    text = (body.text or "").strip() or calls.default_permission_text()
    try:
        message = await whatsapp.request_permission(
            session,
            conversation=conversation,
            contact=contact,
            agent_id=_user_id(ctx),
            text=text,
        )
    except whatsapp.CallError as exc:
        raise _meta_fail(exc) from exc
    return {"message_id": message.id}


@router.post("", status_code=201)
async def create_call(
    body: CallBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    conversation, contact = await _conversation_and_contact(session, ctx, body.conversation_id)
    plan = await calls.recording_plan_for_inbox(session, conversation.inbox_id)
    try:
        call = await whatsapp.start_call(
            session,
            conversation=conversation,
            contact=contact,
            agent_id=_user_id(ctx),
            sdp=body.sdp,
            plan=plan,
        )
    except whatsapp.CallError as exc:
        raise _meta_fail(exc) from exc
    return await calls.present_call(session, call)


@router.get("/{call_id}")
async def show_call(
    call_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    call = await _visible_call(session, ctx, call_id)
    out = await calls.present_call(session, call)
    # The offer only matters to whoever is about to answer.
    if call.status == CALL_RINGING or (
        call.status == CALL_CONNECTING and call.answered_by_id == _user_id(ctx)
    ):
        out["sdp_offer"] = call.sdp_offer
    # The customer's answer only matters to the agent who is calling.
    if call.direction == DIRECTION_OUTBOUND and call.answered_by_id == _user_id(ctx):
        out["sdp_answer"] = call.sdp_answer
    return out


@router.post("/{call_id}/pre_accept")
async def pre_accept_call(
    call_id: Annotated[int, Path()],
    body: AnswerBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    call = await _visible_call(session, ctx, call_id)
    if call.status in FINAL_STATUSES:
        raise _fail(409, "over")
    if not await calls.claim(session, call=call, user_id=_user_id(ctx)):
        raise _fail(409, "over" if call.status in FINAL_STATUSES else "taken")
    try:
        await whatsapp.pre_accept(session, call=call, sdp=body.sdp)
    except whatsapp.CallError as exc:
        # Meta never heard of this agent: the call is free for the others.
        await calls.release(session, call=call)
        raise _meta_fail(exc) from exc
    return await calls.present_call(session, call)


@router.post("/{call_id}/accept")
async def accept_call(
    call_id: Annotated[int, Path()],
    body: AnswerBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    call = await _visible_call(session, ctx, call_id)
    if call.answered_by_id != _user_id(ctx):
        raise _fail(409, "not_yours")
    if call.status == CALL_IN_PROGRESS:
        return await calls.present_call(session, call)
    if call.status != CALL_CONNECTING:
        raise _fail(409, "over")
    plan = await calls.recording_plan(session, call)
    try:
        await whatsapp.accept(session, call=call, sdp=body.sdp, plan=plan)
    except whatsapp.CallError as exc:
        # Meta already has this agent's answer: nobody else can take it.
        # Hang up rather than leave the customer waiting on silence.
        with contextlib.suppress(whatsapp.CallError):
            await whatsapp.terminate(session, call=call)
        await calls.finish(session, call=call, status=CALL_FAILED, reason=exc.detail or exc.code)
        raise _meta_fail(exc) from exc
    await calls.mark_in_progress(
        session,
        call=call,
        record=bool(plan and plan.record),
        transcribe=bool(plan and plan.transcribe),
    )
    return await calls.present_call(session, call)


@router.post("/{call_id}/hangup")
async def hangup_call(
    call_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    call = await _visible_call(session, ctx, call_id)
    if call.status in FINAL_STATUSES:
        return await calls.present_call(session, call)
    if call.answered_by_id != _user_id(ctx) and not ctx.is_administrator:
        raise _fail(409, "not_yours")
    # Already over on Meta's side (the customer hung up first): the call
    # still has to end here.
    with contextlib.suppress(whatsapp.CallError):
        await whatsapp.terminate(session, call=call)
    # Hanging up before the call started leaves it unanswered.
    status = CALL_COMPLETED if call.status == CALL_IN_PROGRESS else CALL_MISSED
    await calls.finish(session, call=call, status=status)
    return await calls.present_call(session, call)
