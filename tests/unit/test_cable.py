"""Unit tests for ``app.core.cable``.

Cover the pure-function protocol pieces — identifier parsing, channel
list selection, envelope decoding. The end-to-end welcome / subscribe
/ broadcast path is covered by the integration test in
``tests/integration/test_cable_router.py`` against real Redis.
"""

from __future__ import annotations

import json

import pytest

from app.core.cable import (
    _decode_envelope,
    _parse_identifier,
    _subscription_channels,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _parse_identifier
# ---------------------------------------------------------------------------
def test_parse_identifier_returns_dict_for_valid_json_object() -> None:
    raw = json.dumps({"channel": "RoomChannel", "pubsub_token": "abc"})
    assert _parse_identifier(raw) == {"channel": "RoomChannel", "pubsub_token": "abc"}


def test_parse_identifier_rejects_non_object_payload() -> None:
    """Rails' identifier is always a JSON object — arrays / scalars are
    invalid and must produce ``reject_subscription``.
    """
    assert _parse_identifier(json.dumps([1, 2, 3])) is None
    assert _parse_identifier(json.dumps("RoomChannel")) is None
    assert _parse_identifier(json.dumps(42)) is None


def test_parse_identifier_rejects_garbage() -> None:
    assert _parse_identifier("not json at all") is None
    assert _parse_identifier("") is None


# ---------------------------------------------------------------------------
# _subscription_channels
# ---------------------------------------------------------------------------
def test_user_subscriber_streams_pubsub_token_and_account_channel() -> None:
    chs = _subscription_channels(
        pubsub_token="user_tok", account_id=42, is_user=True
    )
    assert chs == ["user_tok", "account_42"]


def test_user_subscriber_without_account_only_streams_pubsub_token() -> None:
    """Mirrors Rails ``stream_from "account_..." if @current_account
    .present?`` — without account_id we only subscribe to the user's
    private channel.
    """
    chs = _subscription_channels(
        pubsub_token="user_tok", account_id=None, is_user=True
    )
    assert chs == ["user_tok"]


def test_contact_subscriber_only_streams_pubsub_token() -> None:
    """Contacts (widget visitors) never subscribe to ``account_<id>`` —
    that channel is for User dashboards.
    """
    chs = _subscription_channels(
        pubsub_token="contact_tok", account_id=42, is_user=False
    )
    assert chs == ["contact_tok"]


# ---------------------------------------------------------------------------
# _decode_envelope
# ---------------------------------------------------------------------------
def test_decode_envelope_reads_bytes_payload() -> None:
    """RealtimeBroadcaster publishes UTF-8 bytes; the WS pump reads
    them back and forwards to the client unchanged.
    """
    raw = json.dumps({"event": "x", "data": {"id": 1}}).encode("utf-8")
    assert _decode_envelope(raw) == {"event": "x", "data": {"id": 1}}


def test_decode_envelope_reads_str_payload() -> None:
    """The redis client may return str when ``decode_responses=True`` is
    configured upstream — accept both shapes for robustness.
    """
    raw = json.dumps({"event": "x", "data": {}})
    assert _decode_envelope(raw) == {"event": "x", "data": {}}


def test_decode_envelope_drops_non_dict_payload() -> None:
    assert _decode_envelope(json.dumps([1, 2, 3]).encode()) is None
    assert _decode_envelope(b"not json") is None
    assert _decode_envelope(None) is None
    assert _decode_envelope(42) is None
