"""Unit tests for ``app.core.widget_token``.

Pin the JWT shape that Chatwoot's ``Widget::TokenService`` produces so
a token signed by either backend round-trips through our decoder.
"""

from __future__ import annotations

import pytest

from app.core.widget_token import (
    DEFAULT_EXPIRY_DAYS,
    decode_widget_token,
    encode_widget_token,
)

pytestmark = pytest.mark.unit


def test_roundtrip_returns_payload() -> None:
    token = encode_widget_token(source_id="abc-123", inbox_id=42)
    decoded = decode_widget_token(token)
    assert decoded["source_id"] == "abc-123"
    assert decoded["inbox_id"] == 42
    assert "iat" in decoded and "exp" in decoded
    # Default expiry ~ 180 days from iat.
    assert decoded["exp"] - decoded["iat"] == DEFAULT_EXPIRY_DAYS * 24 * 60 * 60


def test_decode_empty_token_returns_empty_dict() -> None:
    """Mirror Rails ``BaseTokenService#decode_token`` returning ``{}``
    on nil / blank — the widget guard relies on the empty dict to
    skip the contact lookup."""
    assert decode_widget_token(None) == {}
    assert decode_widget_token("") == {}


def test_decode_garbage_returns_empty_dict() -> None:
    """Bad signature / malformed token shouldn't raise."""
    assert decode_widget_token("definitely.not.a.jwt") == {}


def test_decode_expired_returns_empty_dict() -> None:
    """A token with ``exp`` in the past must NOT round-trip — Chatwoot
    relies on this so a leaked token can't be replayed indefinitely."""
    token = encode_widget_token(
        source_id="x", inbox_id=1, ttl_days=0
    )
    # Simulate a tiny delay — the iat stamp is current second, exp is
    # current second + 0 days = the same second. ``leeway=0`` (PyJWT
    # default) treats exp <= now as expired.
    import time

    time.sleep(1)
    assert decode_widget_token(token) == {}
