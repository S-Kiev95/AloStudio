"""Tiny client for the Greenmail HTTP control API.

Greenmail exposes a small REST surface on port 8081 that lets tests:
  * GET /api/service/readiness — health check.
  * POST /api/service/reset — drop every mailbox + every queued mail.
  * GET /api/user/<email>/messages — list messages received by a user.
  * GET /api/mail/<id>/raw — fetch the raw RFC-2822 source of a mail.

We wrap the bits we need so individual tests don't repeat the
boilerplate. The client uses ``httpx`` (already a project dep) and is
sync — every call happens between async test steps where blocking is
fine.
"""

from __future__ import annotations

from typing import Any

import httpx

GREENMAIL_API = "http://127.0.0.1:8081/api"
GREENMAIL_SMTP_HOST = "127.0.0.1"
GREENMAIL_SMTP_PORT = 3025
GREENMAIL_IMAP_HOST = "127.0.0.1"
GREENMAIL_IMAP_PORT = 3143


def reset() -> None:
    """Drop every mailbox + every queued message.

    Called from a per-test teardown hook so tests don't see each
    other's mail. Greenmail's ``/api/service/reset`` is idempotent and
    fast (under 5ms in our local tests).
    """
    httpx.post(f"{GREENMAIL_API}/service/reset", timeout=5.0).raise_for_status()


def messages_for(email: str) -> list[dict[str, Any]]:
    """Return Greenmail's view of every message a recipient has."""
    resp = httpx.get(
        f"{GREENMAIL_API}/user/{email}/messages",
        headers={"Accept": "application/json"},
        timeout=5.0,
    )
    if resp.status_code in (400, 404):
        # Greenmail returns 400 ``"User '...' not found"`` when no mail
        # has landed for that recipient yet. 404 covers older releases.
        # Either is "no mail" — caller wants an empty list.
        return []
    resp.raise_for_status()
    body = resp.json()
    return body if isinstance(body, list) else []


def raw_message(message_id: int | str) -> str:
    """Fetch the raw RFC-2822 source of a mail by Greenmail's id."""
    resp = httpx.get(
        f"{GREENMAIL_API}/mail/{message_id}",
        timeout=5.0,
    )
    resp.raise_for_status()
    body = resp.json()
    if isinstance(body, dict):
        return str(body.get("mimeMessage") or "")
    return ""


def latest_message_to(email: str) -> dict[str, Any] | None:
    """Convenience: pop the most recent mail addressed to ``email``."""
    msgs = messages_for(email)
    return msgs[-1] if msgs else None


__all__ = [
    "GREENMAIL_API",
    "GREENMAIL_IMAP_HOST",
    "GREENMAIL_IMAP_PORT",
    "GREENMAIL_SMTP_HOST",
    "GREENMAIL_SMTP_PORT",
    "latest_message_to",
    "messages_for",
    "raw_message",
    "reset",
]
