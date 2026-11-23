"""Google's OAuth token endpoint and the Calendar API (v3), over httpx."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
SCOPES = "openid email https://www.googleapis.com/auth/calendar.events"

_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


class GoogleError(RuntimeError):
    """``code`` is ``revoked`` when the refresh token no longer works."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200]
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return str(err.get("message") or err.get("status") or "")[:200]
    return str(err or body)[:200]


async def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """The tokens for an authorization code, plus the address in its ID token."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code >= 400:
        raise GoogleError("exchange", _detail(resp))
    tokens = resp.json()
    email = None
    id_token = tokens.get("id_token")
    if isinstance(id_token, str) and id_token.count(".") == 2:
        part = id_token.split(".")[1]
        try:
            claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
            email = claims.get("email")
        except ValueError:
            email = None
    return {"refresh_token": tokens.get("refresh_token"), "email": email}


async def access_token(refresh_token: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code == 400 and "invalid_grant" in resp.text:
        raise GoogleError("revoked")
    if resp.status_code >= 400:
        raise GoogleError("token", _detail(resp))
    return str(resp.json()["access_token"])


async def save_event(token: str, event_id: str | None, body: dict[str, Any]) -> str:
    """Create the event, or replace it; the event's id. An event deleted on
    Google's side is made again."""
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        if event_id:
            resp = await client.put(f"{EVENTS_URL}/{event_id}", headers=headers, json=body)
            if resp.status_code not in (404, 410):
                if resp.status_code >= 400:
                    raise GoogleError("event", _detail(resp))
                return str(resp.json()["id"])
        resp = await client.post(EVENTS_URL, headers=headers, json=body)
    if resp.status_code >= 400:
        raise GoogleError("event", _detail(resp))
    return str(resp.json()["id"])


async def delete_event(token: str, event_id: str) -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.delete(
            f"{EVENTS_URL}/{event_id}", headers={"Authorization": f"Bearer {token}"}
        )
    if resp.status_code >= 400 and resp.status_code not in (404, 410):
        raise GoogleError("event", _detail(resp))


async def revoke(token: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(REVOKE_URL, data={"token": token})
    except httpx.HTTPError as exc:
        log.warning("google_calendar.revoke_failed err=%s", type(exc).__name__)


__all__ = [
    "AUTHORIZE_URL",
    "SCOPES",
    "GoogleError",
    "access_token",
    "delete_event",
    "exchange_code",
    "revoke",
    "save_event",
]
