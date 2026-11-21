"""WhatsApp calls (F7): Meta's Business Calling API.

Meta announces a call on the ``calls`` webhook field: ``connect`` carries the
caller's WebRTC offer, ``terminate`` the end (status, and the length when
somebody answered). The agent's browser builds the answer; we hand it to
Meta in two steps, ``pre_accept`` (the audio path forms) and ``accept``
(the call starts), and ``terminate`` hangs up. Audio never passes through
the server: it goes between Meta and the browser.

Docs: developers.facebook.com/docs/whatsapp/cloud-api/calling
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.calls import service as calls
from app.domains.calls.models import (
    CALL_COMPLETED,
    CALL_FAILED,
    CALL_IN_PROGRESS,
    CALL_MISSED,
    PROVIDER_WHATSAPP,
    Call,
    CallInboxSettings,
)
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import Message
from app.domains.conversations.service import MessageBuilderParams, create_message
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    WHATSAPP_PROVIDER_CLOUD,
    Inbox,
    WhatsappChannel,
)
from app.domains.whatsapp.cloud_provider import _api_base as _cloud_api_base
from app.domains.whatsapp.media import _download_cloud_media, download_and_store_media

log = logging.getLogger(__name__)

_DAYS = ("SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY")


class CallError(Exception):
    """Something kept Meta from doing what we asked. ``code`` is what the
    panel translates: ``not_connected`` (no Cloud number or token),
    ``unreachable`` (Meta did not answer), ``no_permission`` (the customer
    has not allowed calls), ``limit`` (Meta's call or request limits),
    ``window`` (a free-form message outside the 24 hours), ``refused`` (Meta
    said no; its reason is in ``detail``)."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# Talking to Meta
# ---------------------------------------------------------------------------
# Meta's error codes the panel explains in its own words.
_META_CODES: dict[Any, str] = {
    138006: "no_permission",  # no call permission from the customer
    138037: "limit",  # calls placed above the number's limit
    138009: "limit",  # permission requests above the daily/weekly limit
    131047: "window",  # free-form message more than 24 hours after theirs
}
def _credentials(channel: WhatsappChannel) -> tuple[str, str]:
    """``(phone_number_id, token)`` of a connected Cloud number."""
    cfg = channel.provider_config if isinstance(channel.provider_config, dict) else {}
    pnid, token = cfg.get("phone_number_id"), cfg.get("api_key")
    if channel.provider != WHATSAPP_PROVIDER_CLOUD or not pnid or not token:
        raise CallError("not_connected")
    return str(pnid), str(token)


async def _graph(
    channel: WhatsappChannel, method: str, edge: str, *, json: dict[str, Any] | None = None
) -> dict[str, Any]:
    pnid, token = _credentials(channel)
    url = f"{_cloud_api_base()}/{get_settings().meta_graph_api_version}/{pnid}/{edge}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(
                method, url, json=json, headers={"Authorization": f"Bearer {token}"}
            )
    except httpx.HTTPError as exc:
        raise CallError("unreachable") from exc
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code >= 400 or not isinstance(body, dict):
        error = body.get("error") if isinstance(body, dict) else None
        detail = None
        if isinstance(error, dict):
            detail = (
                (error.get("error_data") or {}).get("details")
                if isinstance(error.get("error_data"), dict)
                else None
            ) or error.get("error_user_msg") or error.get("message")
        log.warning(
            "calls.whatsapp.api_error channel_id=%s edge=%s status=%s body=%s",
            channel.id,
            edge,
            resp.status_code,
            resp.text[:300],
        )
        meta_code = error.get("code") if isinstance(error, dict) else None
        raise CallError(_META_CODES.get(meta_code, "refused"), str(detail) if detail else None)
    return body


async def _call_action(
    channel: WhatsappChannel,
    *,
    call: Call,
    action: str,
    sdp: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    body: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "call_id": call.provider_call_id,
        "action": action,
    }
    if sdp is not None:
        body["session"] = {"sdp_type": "answer", "sdp": sdp}
    if extra:
        body.update(extra)
    await _graph(channel, "POST", "calls", json=body)


def media_request(plan: CallInboxSettings | None) -> dict[str, Any]:
    """The ``recording`` / ``transcription`` objects for ``accept``. Meta
    reads ``purpose`` to both sides before it starts recording."""
    if plan is None:
        return {}
    notice = {
        "status": "ENABLED",
        "purpose": (plan.purpose or calls.default_purpose())[:250],
        "announcement_language": plan.announcement_language or "es",
    }
    out: dict[str, Any] = {}
    if plan.record:
        out["recording"] = dict(notice)
    if plan.transcribe:
        out["transcription"] = dict(notice)
    return out


async def channel_for(session: AsyncSession, call: Call) -> WhatsappChannel:
    inbox = await session.get(Inbox, call.inbox_id)
    channel = await session.get(WhatsappChannel, inbox.channel_id) if inbox else None
    if channel is None:
        raise CallError("not_connected")
    return channel


async def pre_accept(session: AsyncSession, *, call: Call, sdp: str) -> None:
    await _call_action(await channel_for(session, call), call=call, action="pre_accept", sdp=sdp)


async def accept(
    session: AsyncSession, *, call: Call, sdp: str, plan: CallInboxSettings | None = None
) -> None:
    await _call_action(
        await channel_for(session, call),
        call=call,
        action="accept",
        sdp=sdp,
        extra=media_request(plan),
    )


async def terminate(session: AsyncSession, *, call: Call) -> None:
    await _call_action(await channel_for(session, call), call=call, action="terminate")


# ---------------------------------------------------------------------------
# Webhook: the ``calls`` field
# ---------------------------------------------------------------------------
def _caller(item: dict[str, Any], contacts_block: list[Any]) -> str | None:
    raw = item.get("from")
    if not raw:
        for c in contacts_block:
            if isinstance(c, dict) and c.get("wa_id"):
                raw = c["wa_id"]
                break
    if not raw:
        return None
    raw = str(raw)
    return raw if raw.startswith("+") else f"+{raw}"


def _profile_name(phone: str, contacts_block: list[Any]) -> str | None:
    bare = phone.lstrip("+")
    for c in contacts_block:
        if not isinstance(c, dict) or str(c.get("wa_id") or "").lstrip("+") != bare:
            continue
        profile = c.get("profile")
        if isinstance(profile, dict) and profile.get("name"):
            return str(profile["name"])
    return None


async def _on_connect(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    item: dict[str, Any],
    contacts_block: list[Any],
) -> None:
    call_id = item.get("id")
    if not call_id:
        return
    if str(item.get("direction") or "USER_INITIATED") == "BUSINESS_INITIATED":
        await _on_outbound_connect(session, item=item)
        return
    phone = _caller(item, contacts_block)
    if phone is None:
        log.info("calls.whatsapp.skip reason=no_caller call_id=%s", call_id)
        return
    if await calls.by_provider_id(session, str(call_id)) is not None:
        return
    # The same contact and conversation a message from this number lands in.
    from app.domains.whatsapp.incoming_cloud import (
        _find_or_create_contact,
        _find_or_create_conversation,
    )

    contact = await _find_or_create_contact(
        session,
        account_id=channel.account_id,
        phone_number=phone,
        name=_profile_name(phone, contacts_block),
    )
    contact_inbox = await ContactInboxBuilder(
        session=session, contact=contact, inbox=inbox, source_id=phone
    ).perform()
    conversation = await _find_or_create_conversation(session, contact_inbox=contact_inbox)
    session_block = item.get("session")
    offer = None
    if isinstance(session_block, dict) and session_block.get("sdp_type") == "offer":
        offer = str(session_block.get("sdp") or "") or None
    await calls.start_inbound(
        session,
        conversation=conversation,
        contact=contact,
        provider=PROVIDER_WHATSAPP,
        provider_call_id=str(call_id),
        from_number=phone,
        to_number=str(item.get("to") or "") or channel.phone_number,
        sdp_offer=offer,
    )


def _timestamp(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _meta_status(item: dict[str, Any]) -> str:
    status = item.get("status")
    if isinstance(status, list):  # one sample in the docs sends a list
        status = status[0] if status else ""
    return str(status or "").upper()


async def _on_terminate(
    session: AsyncSession, *, item: dict[str, Any], errors: list[Any]
) -> None:
    call_id = item.get("id")
    if not call_id:
        return
    call = await calls.by_provider_id(session, str(call_id))
    if call is None:
        return
    duration = item.get("duration")
    try:
        duration_seconds = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_seconds = None
    picked_up = duration_seconds is not None or item.get("start_time") is not None
    reason = None
    if errors and isinstance(errors[0], dict):
        err = errors[0]
        reason = f"{err.get('code')}: {err.get('message') or err.get('title') or ''}".strip()
    if _meta_status(item) == "FAILED":
        status = CALL_FAILED
    elif picked_up or call.status == CALL_IN_PROGRESS:
        status = CALL_COMPLETED
    else:
        status = CALL_MISSED
    await calls.finish(
        session,
        call=call,
        status=status,
        ended_at=_timestamp(item.get("end_time")) or _timestamp(item.get("timestamp")),
        duration_seconds=duration_seconds,
        reason=reason,
    )


# Meta's reference says ``call_transcription_available``; what it really
# sends (staging, 2026-11-20) is ``call_transcript_available``. Both count.
_MEDIA_EVENTS = (
    "call_recording_available",
    "call_transcript_available",
    "call_transcription_available",
)


async def process_calls_value(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    value: dict[str, Any],
) -> None:
    """One ``calls`` change of a Cloud webhook."""
    contacts_block = value.get("contacts") if isinstance(value.get("contacts"), list) else []
    errors = value.get("errors") if isinstance(value.get("errors"), list) else []
    for status in value.get("statuses") or []:
        if isinstance(status, dict) and status.get("type") == "call":
            try:
                async with session.begin_nested():
                    await _on_call_status(session, status=status)
            except Exception:
                log.exception("calls.whatsapp.status_failed call_id=%s", status.get("id"))
    for item in value.get("calls") or []:
        if not isinstance(item, dict):
            continue
        event = item.get("event")
        # What Meta sends for each call (no audio, text or numbers): enough
        # to tell a missing transcript from one we failed to read.
        log.info(
            "calls.whatsapp.event event=%s call=%s fields=%s",
            event,
            item.get("id"),
            ",".join(sorted(k for k in item if k not in ("from", "to", "session"))),
        )
        try:
            async with session.begin_nested():
                if event == "connect":
                    await _on_connect(
                        session,
                        channel=channel,
                        inbox=inbox,
                        item=item,
                        contacts_block=contacts_block or [],
                    )
                elif event == "terminate":
                    await _on_terminate(session, item=item, errors=errors or [])
                elif event in _MEDIA_EVENTS:
                    await _on_media(session, channel=channel, item=item)
        except Exception:
            log.exception(
                "calls.whatsapp.event_failed event=%s call_id=%s", event, item.get("id")
            )


# ---------------------------------------------------------------------------
# Recording and transcript
# ---------------------------------------------------------------------------
async def _on_media(session: AsyncSession, *, channel: WhatsappChannel, item: dict[str, Any]) -> None:
    """Meta finished a call's recording or transcript. Note it, then copy it
    now; the tick retries if the copy fails (Meta keeps it 7 days)."""
    call = await calls.by_provider_id(session, str(item.get("id") or ""))
    if call is None:
        return
    if item.get("event") == "call_recording_available":
        media = (item.get("call_recording") or {}).get("audio") or {}
        kind = "recording"
    else:
        media = (item.get("call_transcript") or {}).get("document") or {}
        kind = "transcript"
    media_id = media.get("id") if isinstance(media, dict) else None
    if not media_id:
        return
    await calls.media_announced(session, call=call, kind=kind, media_id=str(media_id))
    await fetch_media(session, call=call, channel=channel)


async def fetch_media(
    session: AsyncSession, *, call: Call, channel: WhatsappChannel | None = None
) -> None:
    """Copy whatever of this call Meta has and we do not. Best effort: a
    failure leaves the media id for the next try."""
    channel = channel or await channel_for(session, call)
    if call.recording_media_id:
        stored = await download_and_store_media(
            channel, account_id=call.account_id, media_id=call.recording_media_id
        )
        if stored is not None and stored.get("external_url"):
            await calls.attach_recording(
                session,
                call=call,
                external_url=str(stored["external_url"]),
                extension=stored.get("extension"),
            )
        else:
            log.warning("calls.whatsapp.recording_copy_failed call_id=%s", call.id)
    if call.transcript_media_id:
        downloaded = await _download_cloud_media(channel, call.transcript_media_id)
        if downloaded is None:
            log.warning("calls.whatsapp.transcript_copy_failed call_id=%s", call.id)
            return
        try:
            document = json.loads(downloaded[0].decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            log.warning("calls.whatsapp.transcript_unreadable call_id=%s", call.id)
            return
        segments, language = parse_transcript(document)
        await calls.save_transcript(session, call=call, segments=segments, language=language)


async def retry_pending_media(session: AsyncSession) -> int:
    """Run by the 5-minute tick: copies that failed when Meta announced them."""
    done = 0
    for call in await calls.pending_media(session):
        try:
            async with session.begin_nested():
                await fetch_media(session, call=call)
            done += 1
        except Exception:
            log.exception("calls.whatsapp.media_retry_failed call_id=%s", call.id)
    return done


_MARKER = re.compile(r"\[(Business|Customer)\]", re.IGNORECASE)


def _speaker(raw: Any, channel_no: Any) -> str:
    text = str(raw or "").lower()
    if text.startswith("bus") or channel_no == 0:
        return "business"
    return "customer"


def parse_transcript(document: Any) -> tuple[list[dict[str, Any]], str | None]:
    """Meta's transcript JSON → ``[{speaker, text, start}]`` and its language.
    ``speaker`` is ``business`` (the agent) or ``customer``."""
    root = document.get("transcript") if isinstance(document, dict) else None
    if not isinstance(root, dict):
        root = document if isinstance(document, dict) else {}
    language = root.get("language") if isinstance(root.get("language"), str) else None
    out: list[dict[str, Any]] = []
    raw_segments = root.get("segments")
    for seg in raw_segments if isinstance(raw_segments, list) else []:
        if not isinstance(seg, dict):
            continue
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        start = seg.get("start")
        out.append(
            {
                "speaker": _speaker(seg.get("speaker"), seg.get("channel")),
                "text": text,
                "start": float(start) if isinstance(start, int | float) else None,
            }
        )
    if not out and isinstance(root.get("text"), str):
        # Only the flat text: "[Business] Hola … [Customer] Buenas …"
        parts = _MARKER.split(root["text"])
        for who, said in zip(parts[1::2], parts[2::2], strict=False):
            said = said.strip()
            if said:
                out.append({"speaker": _speaker(who, None), "text": said, "start": None})
    return out, language


# ---------------------------------------------------------------------------
# Calls we make
# ---------------------------------------------------------------------------
def _digits(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())


def _unix(value: Any) -> int | None:
    """Meta sends times as Unix seconds, as a number or a string."""
    text = str(value) if value is not None else ""
    return int(text) if text.isdigit() else None


async def _conversation_channel(
    session: AsyncSession, conversation: Any
) -> WhatsappChannel:
    inbox = await session.get(Inbox, conversation.inbox_id)
    if inbox is None or inbox.channel_type != CHANNEL_TYPE_WHATSAPP:
        raise CallError("not_connected")
    channel = await session.get(WhatsappChannel, inbox.channel_id)
    if channel is None:
        raise CallError("not_connected")
    _credentials(channel)
    return channel


async def permission_state(
    session: AsyncSession, *, conversation: Any, contact: Contact
) -> dict[str, Any]:
    """Whether this customer lets the business call them, as Meta keeps it:
    ``status`` ``no_permission`` / ``temporary`` / ``permanent``, until when,
    and whether a call or a permission request can go out now."""
    channel = await _conversation_channel(session, conversation)
    phone = _digits(contact.phone_number or "")
    if not phone:
        raise CallError("no_phone")
    pnid, token = _credentials(channel)
    url = f"{_cloud_api_base()}/{get_settings().meta_graph_api_version}/{pnid}/call_permissions"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url, params={"user_wa_id": phone}, headers={"Authorization": f"Bearer {token}"}
            )
    except httpx.HTTPError as exc:
        raise CallError("unreachable") from exc
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code >= 400 or not isinstance(body, dict):
        error = body.get("error") if isinstance(body, dict) else None
        detail = error.get("message") if isinstance(error, dict) else None
        meta_code = error.get("code") if isinstance(error, dict) else None
        raise CallError(_META_CODES.get(meta_code, "refused"), detail)
    raw_permission = body.get("permission")
    permission: dict[str, Any] = raw_permission if isinstance(raw_permission, dict) else {}
    actions = {
        a.get("action_name"): a
        for a in body.get("actions") or []
        if isinstance(a, dict)
    }

    def allowed(name: str) -> bool:
        action = actions.get(name)
        return bool(action and action.get("can_perform_action"))

    expiration = permission.get("expiration_time") or permission.get("expiration")
    return {
        "status": permission.get("status") or "no_permission",
        "expires_at": _unix(expiration),
        "can_call": allowed("start_call"),
        "can_request": allowed("send_call_permission_request"),
    }


async def request_permission(
    session: AsyncSession,
    *,
    conversation: Any,
    contact: Contact,
    agent_id: int,
    text: str,
) -> Message:
    """Ask the customer, in the chat, whether the business may call them.
    WhatsApp shows it with its own buttons; the answer comes back as a
    message (:func:`permission_reply`)."""
    channel = await _conversation_channel(session, conversation)
    phone = _digits(contact.phone_number or "")
    if not phone:
        raise CallError("no_phone")
    body = await _graph(
        channel,
        "POST",
        "messages",
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "call_permission_request",
                "action": {"name": "call_permission_request"},
                "body": {"text": text},
            },
        },
    )
    sent = body.get("messages") if isinstance(body.get("messages"), list) else []
    wamid = sent[0].get("id") if sent and isinstance(sent[0], dict) else None
    return await create_message(
        session,
        conversation=conversation,
        params=MessageBuilderParams(
            content=text,
            message_type="outgoing",
            # Sent already, through Meta; the reply cascade must not resend it.
            content_attributes={"external_echo": True, "call_permission_request": True},
            source_id=str(wamid) if wamid else None,
        ),
        user_id=agent_id,
    )


async def start_call(
    session: AsyncSession,
    *,
    conversation: Any,
    contact: Contact,
    agent_id: int,
    sdp: str,
    plan: CallInboxSettings | None = None,
) -> Call:
    """Ring the customer with the offer the agent's browser made."""
    channel = await _conversation_channel(session, conversation)
    phone = _digits(contact.phone_number or "")
    if not phone:
        raise CallError("no_phone")
    body = await _graph(
        channel,
        "POST",
        "calls",
        json={
            "messaging_product": "whatsapp",
            "to": phone,
            "action": "connect",
            "session": {"sdp_type": "offer", "sdp": sdp},
            **media_request(plan),
        },
    )
    placed = body.get("calls") if isinstance(body.get("calls"), list) else []
    call_id = placed[0].get("id") if placed and isinstance(placed[0], dict) else None
    if not call_id:
        raise CallError("refused")
    return await calls.start_outbound(
        session,
        conversation=conversation,
        contact=contact,
        agent_id=agent_id,
        provider=PROVIDER_WHATSAPP,
        provider_call_id=str(call_id),
        from_number=channel.phone_number,
        to_number=contact.phone_number,
        record=bool(plan and plan.record),
        transcribe=bool(plan and plan.transcribe),
    )


async def _on_outbound_connect(session: AsyncSession, *, item: dict[str, Any]) -> None:
    call = await calls.by_provider_id(session, str(item.get("id") or ""))
    if call is None:
        return
    session_block = item.get("session")
    if isinstance(session_block, dict) and session_block.get("sdp_type") == "answer":
        sdp = str(session_block.get("sdp") or "")
        if sdp:
            await calls.save_answer(session, call=call, sdp=sdp)


async def _on_call_status(session: AsyncSession, *, status: dict[str, Any]) -> None:
    """RINGING / ACCEPTED / REJECTED for a call we made."""
    call = await calls.by_provider_id(session, str(status.get("id") or ""))
    if call is None:
        return
    state = str(status.get("status") or "").upper()
    if state == "ACCEPTED":
        await calls.customer_answered(session, call=call)
    elif state == "REJECTED":
        await calls.finish(session, call=call, status=CALL_MISSED, reason="rejected")


def permission_reply(message: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """A customer's answer to "can we call you?" (or the permission WhatsApp
    gives automatically when they call), as the text and attributes of the
    message it becomes. ``None`` for any other interactive message."""
    interactive = message.get("interactive")
    if not isinstance(interactive, dict) or interactive.get("type") != "call_permission_reply":
        return None
    reply = interactive.get("call_permission_reply")
    reply = reply if isinstance(reply, dict) else {}
    accepted = str(reply.get("response") or "").lower() == "accept"
    permanent = bool(reply.get("is_permanent"))
    automatic = str(reply.get("response_source") or "") == "automatic"
    expiration = reply.get("expiration_timestamp")
    if not accepted:
        key = "calls.permission.rejected"
    elif permanent:
        key = "calls.permission.accepted_always"
    elif automatic:
        key = "calls.permission.accepted_by_calling"
    else:
        key = "calls.permission.accepted"
    return t(DEFAULT_LOCALE, key), {
        "call_permission": {
            "response": "accept" if accepted else "reject",
            "permanent": permanent,
            "automatic": automatic,
            "expires_at": _unix(expiration),
        }
    }


# ---------------------------------------------------------------------------
# The number's call settings
# ---------------------------------------------------------------------------
def _hhmm(hour: int | None, minutes: int | None) -> str:
    return f"{int(hour or 0):02d}{int(minutes or 0):02d}"


async def _weekly_hours(session: AsyncSession, inbox: Inbox) -> list[dict[str, str]]:
    """The inbox's business hours in Meta's shape (one entry per open day)."""
    from app.domains.working_hours.models import WorkingHour

    rows = (
        await session.exec(select(WorkingHour).where(WorkingHour.inbox_id == inbox.id))
    ).all()
    out: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda r: r.day_of_week):
        if row.closed_all_day or not 0 <= row.day_of_week <= 6:
            continue
        day = _DAYS[row.day_of_week]
        if row.open_all_day:
            out.append({"day_of_week": day, "open_time": "0000", "close_time": "2359"})
            continue
        opens = _hhmm(row.open_hour, row.open_minutes)
        closes = _hhmm(row.close_hour, row.close_minutes)
        if closes <= opens:  # past midnight: until the end of the day
            closes = "2359"
        if opens != closes:
            out.append({"day_of_week": day, "open_time": opens, "close_time": closes})
    return out


def _all_week() -> list[dict[str, str]]:
    return [{"day_of_week": d, "open_time": "0000", "close_time": "2359"} for d in _DAYS]


async def read_settings(channel: WhatsappChannel) -> dict[str, Any]:
    """The call settings Meta has for the number."""
    body = await _graph(channel, "GET", "settings")
    raw = body.get("calling")
    calling: dict[str, Any] = raw if isinstance(raw, dict) else {}
    raw_hours = calling.get("call_hours")
    hours: dict[str, Any] = raw_hours if isinstance(raw_hours, dict) else {}
    restrictions = calling.get("restrictions")
    return {
        "enabled": calling.get("status") == "ENABLED",
        "call_icon_visible": calling.get("call_icon_visibility") != "DISABLE_ALL",
        "callback_requests": calling.get("callback_permission_status") == "ENABLED",
        "business_hours": hours.get("status") == "ENABLED",
        "restrictions": (
            restrictions.get("restrictions_list")
            if isinstance(restrictions, dict)
            else None
        ),
    }


async def save_settings(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    enabled: bool,
    call_icon_visible: bool,
    callback_requests: bool,
    business_hours: bool,
) -> dict[str, Any]:
    """Turn calls on or off on the number. With ``business_hours`` the
    inbox's hours become the hours people can call; outside them WhatsApp
    offers to ask for a call back (if ``callback_requests``)."""
    weekly = await _weekly_hours(session, inbox) if business_hours else []
    if business_hours and not weekly:
        raise CallError("no_hours")
    calling: dict[str, Any] = {
        "status": "ENABLED" if enabled else "DISABLED",
        "call_icon_visibility": "DEFAULT" if call_icon_visible else "DISABLE_ALL",
        "callback_permission_status": "ENABLED" if callback_requests else "DISABLED",
        "call_hours": {
            "status": "ENABLED" if business_hours else "DISABLED",
            "timezone_id": inbox.timezone or "UTC",
            "weekly_operating_hours": weekly or _all_week(),
        },
    }
    await _graph(channel, "POST", "settings", json={"calling": calling})
    return await read_settings(channel)


__all__ = [
    "CallError",
    "accept",
    "channel_for",
    "fetch_media",
    "media_request",
    "parse_transcript",
    "permission_reply",
    "permission_state",
    "pre_accept",
    "process_calls_value",
    "read_settings",
    "request_permission",
    "retry_pending_media",
    "save_settings",
    "start_call",
    "terminate",
]
