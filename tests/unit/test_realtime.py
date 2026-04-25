"""Unit tests for ``app.core.realtime``.

We don't pull in fakeredis as a dep — the broadcaster's surface area
(``publish`` + ``pipeline``) is tiny enough that a hand-rolled stub
gives faster, more deterministic tests with zero external moving
parts. Integration tests in 4b.6 exercise the real Redis pub/sub end
to end against a testcontainer.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.realtime import RealtimeBroadcaster, encode_envelope

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Stub Redis — implements only the bits ``RealtimeBroadcaster.publish`` needs.
# ---------------------------------------------------------------------------
class _StubPipeline:
    """Mirrors ``redis.asyncio.client.Pipeline`` async-context shape."""

    def __init__(self, sink: list[tuple[str, bytes]]) -> None:
        self._sink = sink
        self._queued: list[tuple[str, bytes]] = []

    async def __aenter__(self) -> "_StubPipeline":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:  # noqa: D401
        return None

    def publish(self, channel: str, payload: bytes) -> "_StubPipeline":
        self._queued.append((channel, payload))
        return self

    async def execute(self) -> list[int]:
        self._sink.extend(self._queued)
        self._queued.clear()
        # Real Redis returns subscriber-counts; we don't care about them.
        return [1] * len(self._sink)


class _StubRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []
        self.closed = False

    def pipeline(self, transaction: bool = False) -> _StubPipeline:
        return _StubPipeline(self.published)

    async def aclose(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# encode_envelope
# ---------------------------------------------------------------------------
def test_encode_envelope_shape() -> None:
    """The envelope is the literal ``{"event": ..., "data": ...}`` byte
    string Chatwoot's ActionCable adapter writes to Redis."""
    payload = encode_envelope("conversation.created", {"id": 7, "status": "open"})
    decoded = json.loads(payload)
    assert decoded == {
        "event": "conversation.created",
        "data": {"id": 7, "status": "open"},
    }


def test_encode_envelope_handles_datetime_and_uuid() -> None:
    """Datetimes -> ISO-8601, UUIDs -> str. Mirrors ActiveSupport::JSON."""
    from datetime import UTC, datetime
    from uuid import UUID

    ts = datetime(2026, 4, 25, 12, 30, 45, tzinfo=UTC)
    uid = UUID("12345678-1234-5678-1234-567812345678")
    payload = encode_envelope("x", {"created_at": ts, "uuid": uid})
    decoded = json.loads(payload)
    assert decoded["data"]["created_at"] == "2026-04-25T12:30:45+00:00"
    assert decoded["data"]["uuid"] == "12345678-1234-5678-1234-567812345678"


# ---------------------------------------------------------------------------
# RealtimeBroadcaster.publish
# ---------------------------------------------------------------------------
async def test_publish_fans_out_to_each_unique_channel() -> None:
    redis = _StubRedis()
    bc = RealtimeBroadcaster(redis)  # type: ignore[arg-type]

    sent = await bc.publish(["agent_token", "contact_token"], "message.created", {"id": 1})

    assert sent == 2
    channels = sorted(ch for ch, _ in redis.published)
    assert channels == ["agent_token", "contact_token"]
    # Same payload bytes on both channels — listener writes once and
    # broadcaster dispatches identically.
    payloads = {p for _, p in redis.published}
    assert len(payloads) == 1
    assert json.loads(next(iter(payloads))) == {
        "event": "message.created",
        "data": {"id": 1},
    }


async def test_publish_dedupes_repeated_channels() -> None:
    """Mirrors ``ActionCableBroadcastJob``'s ``tokens.uniq``."""
    redis = _StubRedis()
    bc = RealtimeBroadcaster(redis)  # type: ignore[arg-type]

    sent = await bc.publish(["t1", "t1", "t2"], "x", {"k": "v"})

    assert sent == 2
    channels = sorted(ch for ch, _ in redis.published)
    assert channels == ["t1", "t2"]


async def test_publish_skips_empty_token_strings() -> None:
    """Some ContactInbox rows nullable-pubsub_token (legacy data); the
    listener-side filter should drop them but the broadcaster also
    defensively skips empty strings — we don't want to PUBLISH on ``""``.
    """
    redis = _StubRedis()
    bc = RealtimeBroadcaster(redis)  # type: ignore[arg-type]

    sent = await bc.publish(["", "t1", ""], "x", {"k": "v"})

    assert sent == 1
    assert [ch for ch, _ in redis.published] == ["t1"]


async def test_publish_with_no_channels_is_a_no_op() -> None:
    """Mirrors ``return if members.blank?`` early-out in
    ``ActionCableBroadcastJob#perform``.
    """
    redis = _StubRedis()
    bc = RealtimeBroadcaster(redis)  # type: ignore[arg-type]

    sent = await bc.publish([], "x", {})

    assert sent == 0
    assert redis.published == []


async def test_close_closes_underlying_redis() -> None:
    redis = _StubRedis()
    bc = RealtimeBroadcaster(redis)  # type: ignore[arg-type]
    await bc.close()
    assert redis.closed is True
