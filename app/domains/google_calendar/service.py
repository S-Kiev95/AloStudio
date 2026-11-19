"""Each agent's Agenda in their own Google Calendar (F17, point 11).

An agent connects from Mi perfil (Google's consent screen, scope
``calendar.events``); from then on the 5-minute tick puts in their primary
calendar the appointments they created and the CRM tasks they own that have
a date, from yesterday to three months ahead. One way only: AloStudio is
where they are edited. Changed ones are updated, and cancelled, done or
deleted ones are taken off.

Needs ``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET`` (Ajustes →
Instalación), the same as signing in with Google, and the redirect
``{APP_BASE_URL}/google-calendar/callback`` added to that Google client.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.oauth_state import sign_oauth_state, verify_oauth_state
from app.domains.appointments.models import (
    APPOINTMENT_STATUS_CANCELLED,
    APPOINTMENT_STATUS_DONE,
    Appointment,
)
from app.domains.contacts.models import Contact
from app.domains.crm.models import CrmActivity
from app.domains.google_calendar import client
from app.domains.google_calendar.models import (
    SOURCE_ACTIVITY,
    SOURCE_APPOINTMENT,
    GoogleCalendarEvent,
    GoogleCalendarLink,
)

log = logging.getLogger(__name__)

CALLBACK_PATH = "/google-calendar/callback"
_FLOW = "google_calendar"
PAST = timedelta(days=1)
AHEAD = timedelta(days=90)
DEFAULT_LENGTH = timedelta(minutes=30)
# Google allows plenty; this keeps one tick short for a first sync.
WRITES_PER_TICK = 60


def available() -> bool:
    settings = get_settings()
    return bool(settings.google_client_id and settings.google_client_secret)


def _fernet() -> Fernet:
    digest = hashlib.sha256(b"google-calendar:" + get_settings().secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _redirect_uri() -> str:
    return get_settings().app_base_url.rstrip("/") + CALLBACK_PATH


def authorize_url(user_id: int) -> str:
    query = {
        "client_id": get_settings().google_client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": client.SCOPES,
        # A refresh token every time, so reconnecting always works.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": sign_oauth_state(0, flow=f"{_FLOW}:{user_id}"),
    }
    return f"{client.AUTHORIZE_URL}?{urlencode(query)}"


async def connect(
    session: AsyncSession, *, user_id: int, code: str, state: str
) -> GoogleCalendarLink:
    """Keep the refresh token of the consent ``user_id`` just gave.
    Raises ``ValueError(code)``."""
    payload = verify_oauth_state(state)
    if payload.get("flow") != f"{_FLOW}:{user_id}":
        raise ValueError("state")
    try:
        tokens = await client.exchange_code(code, _redirect_uri())
    except client.GoogleError as exc:
        log.warning("google_calendar.exchange_failed user_id=%s err=%s", user_id, exc)
        raise ValueError("exchange") from exc
    if not tokens.get("refresh_token"):
        raise ValueError("no_refresh_token")
    link = await session.get(GoogleCalendarLink, user_id)
    if link is None:
        link = GoogleCalendarLink(user_id=user_id, refresh_token_encrypted="")
    link.refresh_token_encrypted = _fernet().encrypt(tokens["refresh_token"].encode()).decode()
    link.google_email = tokens.get("email")
    link.last_error = None
    session.add(link)
    await session.flush()
    return link


def _refresh_token(link: GoogleCalendarLink) -> str:
    try:
        return _fernet().decrypt(link.refresh_token_encrypted.encode()).decode()
    except InvalidToken as exc:
        # The app's secret changed: they connect again.
        raise client.GoogleError("revoked") from exc


async def status(session: AsyncSession, user_id: int) -> dict[str, Any]:
    link = await session.get(GoogleCalendarLink, user_id)
    return {
        "available": available(),
        "connected": link is not None,
        "email": link.google_email if link else None,
        "last_synced_at": link.last_synced_at.isoformat() if link and link.last_synced_at else None,
        "problem": link.last_error if link else None,
    }


async def disconnect(session: AsyncSession, user_id: int) -> None:
    """Take our events off their calendar (best effort), give the access
    back to Google and forget the link."""
    link = await session.get(GoogleCalendarLink, user_id)
    if link is None:
        return
    events = list(
        (
            await session.exec(
                select(GoogleCalendarEvent).where(GoogleCalendarEvent.user_id == user_id)
            )
        ).all()
    )
    try:
        refresh = _refresh_token(link)
        token = await client.access_token(refresh)
        for event in events:
            await client.delete_event(token, event.event_id)
        await client.revoke(refresh)
    except client.GoogleError as exc:
        log.info("google_calendar.disconnect_partial user_id=%s err=%s", user_id, exc)
    for event in events:
        await session.delete(event)
    await session.delete(link)
    await session.flush()


def _when(at: datetime) -> dict[str, str]:
    return {"dateTime": at.astimezone(UTC).isoformat()}


def _fingerprint(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


async def _wanted(session: AsyncSession, user_id: int) -> dict[tuple[str, int], dict[str, Any]]:
    """The events the user's calendar should have, by (source, id)."""
    now = datetime.now(UTC)
    since, until = now - PAST, now + AHEAD
    base = get_settings().app_base_url.rstrip("/")
    appointments = (
        await session.exec(
            select(Appointment).where(
                Appointment.created_by_id == user_id,
                col(Appointment.status).not_in(
                    [APPOINTMENT_STATUS_CANCELLED, APPOINTMENT_STATUS_DONE]
                ),
                Appointment.starts_at >= since,
                Appointment.starts_at <= until,
            )
        )
    ).all()
    tasks = (
        await session.exec(
            select(CrmActivity).where(
                CrmActivity.owner_id == user_id,
                col(CrmActivity.done_at).is_(None),
                col(CrmActivity.due_at).is_not(None),
                col(CrmActivity.due_at) >= since,
                col(CrmActivity.due_at) <= until,
            )
        )
    ).all()
    contact_ids = {a.contact_id for a in appointments} | {
        t.contact_id for t in tasks if t.contact_id
    }
    names: dict[int, str] = {}
    if contact_ids:
        rows = await session.exec(
            select(Contact.id, Contact.name).where(col(Contact.id).in_(contact_ids))
        )
        names = {cid: name for cid, name in rows.all() if cid is not None and name}

    def link_to(account_id: int, contact_id: int | None) -> str:
        if contact_id is None:
            return f"{base}/accounts/{account_id}/agenda"
        return f"{base}/accounts/{account_id}/contacts/{contact_id}"

    wanted: dict[tuple[str, int], dict[str, Any]] = {}
    for a in appointments:
        assert a.id is not None
        who = names.get(a.contact_id)
        text = "\n\n".join(p for p in (a.description, a.notes) if p)
        wanted[(SOURCE_APPOINTMENT, a.id)] = {
            "summary": f"{a.title} · {who}" if who else a.title,
            "description": f"{text}\n\n{link_to(a.account_id, a.contact_id)}".strip(),
            "start": _when(a.starts_at),
            "end": _when(a.ends_at or a.starts_at + DEFAULT_LENGTH),
            "source": {"title": "AloStudio", "url": link_to(a.account_id, a.contact_id)},
        }
    for task in tasks:
        assert task.id is not None and task.due_at is not None
        who = names.get(task.contact_id) if task.contact_id else None
        wanted[(SOURCE_ACTIVITY, task.id)] = {
            "summary": f"{task.title} · {who}" if who else task.title,
            "description": f"{task.description or ''}\n\n{link_to(task.account_id, task.contact_id)}".strip(),
            "start": _when(task.due_at),
            "end": _when(task.due_at + DEFAULT_LENGTH),
            "source": {"title": "AloStudio", "url": link_to(task.account_id, task.contact_id)},
        }
    return wanted


async def sync_user(session: AsyncSession, link: GoogleCalendarLink) -> int:
    """Bring one calendar in line; how many events were written or removed."""
    try:
        token = await client.access_token(_refresh_token(link))
    except client.GoogleError as exc:
        link.last_error = exc.code
        session.add(link)
        await session.flush()
        return 0
    wanted = await _wanted(session, link.user_id)
    have = {
        (e.source, e.source_id): e
        for e in (
            await session.exec(
                select(GoogleCalendarEvent).where(GoogleCalendarEvent.user_id == link.user_id)
            )
        ).all()
    }
    writes = 0
    try:
        for key, event in list(have.items()):
            if key in wanted or writes >= WRITES_PER_TICK:
                continue
            await client.delete_event(token, event.event_id)
            await session.delete(event)
            writes += 1
        for key, body in wanted.items():
            if writes >= WRITES_PER_TICK:
                break
            fingerprint = _fingerprint(body)
            current = have.get(key)
            if current is not None and current.fingerprint == fingerprint:
                continue
            event_id = await client.save_event(token, current.event_id if current else None, body)
            if current is None:
                current = GoogleCalendarEvent(
                    user_id=link.user_id,
                    source=key[0],
                    source_id=key[1],
                    event_id=event_id,
                    fingerprint=fingerprint,
                )
            current.event_id, current.fingerprint = event_id, fingerprint
            session.add(current)
            writes += 1
        link.last_error = None
    except client.GoogleError as exc:
        log.warning("google_calendar.sync_failed user_id=%s err=%s", link.user_id, exc)
        link.last_error = str(exc)[:200]
    link.last_synced_at = datetime.now(UTC)
    session.add(link)
    await session.flush()
    return writes


async def sync_all(session: AsyncSession) -> int:
    """Run by the 5-minute tick."""
    if not available():
        return 0
    links = (
        await session.exec(
            select(GoogleCalendarLink).where(
                col(GoogleCalendarLink.last_error).is_distinct_from("revoked")
            )
        )
    ).all()
    done = 0
    for link in links:
        try:
            async with session.begin_nested():
                done += await sync_user(session, link)
        except Exception:
            log.exception("google_calendar.sync_crashed user_id=%s", link.user_id)
    return done


__all__ = [
    "CALLBACK_PATH",
    "authorize_url",
    "available",
    "connect",
    "disconnect",
    "status",
    "sync_all",
    "sync_user",
]
