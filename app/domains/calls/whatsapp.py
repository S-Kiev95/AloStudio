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

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.calls import service as calls
from app.domains.calls.models import (
    CALL_COMPLETED,
    CALL_FAILED,
    CALL_IN_PROGRESS,
    CALL_MISSED,
    PROVIDER_WHATSAPP,
    Call,
)
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD, Inbox, WhatsappChannel
from app.domains.whatsapp.cloud_provider import _api_base as _cloud_api_base

log = logging.getLogger(__name__)

_DAYS = ("SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY")


class CallError(Exception):
    """Something kept Meta from doing what we asked. ``code`` is what the
    panel translates: ``not_connected`` (no Cloud number or token),
    ``unreachable`` (Meta did not answer), ``refused`` (Meta said no; its
    reason is in ``detail``)."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# Talking to Meta
# ---------------------------------------------------------------------------
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
        raise CallError("refused", str(detail) if detail else None)
    return body


async def _call_action(
    channel: WhatsappChannel, *, call: Call, action: str, sdp: str | None = None
) -> None:
    body: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "call_id": call.provider_call_id,
        "action": action,
    }
    if sdp is not None:
        body["session"] = {"sdp_type": "answer", "sdp": sdp}
    await _graph(channel, "POST", "calls", json=body)


async def channel_for(session: AsyncSession, call: Call) -> WhatsappChannel:
    inbox = await session.get(Inbox, call.inbox_id)
    channel = await session.get(WhatsappChannel, inbox.channel_id) if inbox else None
    if channel is None:
        raise CallError("not_connected")
    return channel


async def pre_accept(session: AsyncSession, *, call: Call, sdp: str) -> None:
    await _call_action(await channel_for(session, call), call=call, action="pre_accept", sdp=sdp)


async def accept(session: AsyncSession, *, call: Call, sdp: str) -> None:
    await _call_action(await channel_for(session, call), call=call, action="accept", sdp=sdp)


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
    if str(item.get("direction") or "USER_INITIATED") != "USER_INITIATED":
        return  # calls we make: next step of F7
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
    for item in value.get("calls") or []:
        if not isinstance(item, dict):
            continue
        event = item.get("event")
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
        except Exception:
            log.exception(
                "calls.whatsapp.event_failed event=%s call_id=%s", event, item.get("id")
            )


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
    "pre_accept",
    "process_calls_value",
    "read_settings",
    "save_settings",
    "terminate",
]
