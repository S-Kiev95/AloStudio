"""Signed OAuth ``state`` — CSRF protection that also carries the account
(and the flow) through a provider's redirect, whose callback has no
session to trust."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException


def _state_secret() -> bytes:
    return get_settings().secret_key.encode()


def sign_oauth_state(account_id: int, *, flow: str) -> str:
    """Sign ``{account_id, flow, nonce, ts}`` so the (account-less)
    callback can trust it. HMAC-SHA256 over the base64 payload with the
    app secret key."""
    payload = {
        "account_id": account_id,
        "flow": flow,
        "nonce": secrets.token_hex(8),
        "ts": int(time.time()),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    b = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = hmac.new(
        _state_secret(), b.encode(), hashlib.sha256
    ).hexdigest()[:32]
    return f"{b}.{sig}"


def verify_oauth_state(state: str, *, max_age_seconds: int = 600) -> dict[str, Any]:
    """Verify the signed state → its payload, or 401."""
    try:
        b, sig = state.split(".", 1)
    except (ValueError, AttributeError):
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "invalid oauth state"}
        ) from None
    expected = hmac.new(
        _state_secret(), b.encode(), hashlib.sha256
    ).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig):
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "invalid oauth state"}
        )
    try:
        raw = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4))
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "invalid oauth state"}
        ) from None
    if int(time.time()) - int(payload.get("ts", 0)) > max_age_seconds:
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "oauth state expired"}
        )
    return payload


__all__ = ["sign_oauth_state", "verify_oauth_state"]
