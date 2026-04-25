"""Realtime Redis pub/sub broadcaster.

Ports Chatwoot's ``ActionCable.server.broadcast(channel, payload)`` call
(which ``ActionCableBroadcastJob`` issues once per token) to an async
Redis publisher.

Wire shape on the Redis channel — byte-for-byte identical to what the
Rails ActionCable adapter / anycable-go writes:

    PUBLISH <channel> <json-encoded {"event": ..., "data": ...}>

Downstream consumers:
  * our own ``/cable`` WebSocket handler (Phase 4b.2) subscribes via
    ``redis.asyncio.pubsub`` and forwards frames to its clients.
  * any external anycable-go that happens to share the same Redis.

The client is lazily instantiated against ``settings.redis_url`` and
kept as a module-level singleton. Tests can install a pre-built
broadcaster (e.g. fakeredis-backed or a stub) via
:func:`set_broadcaster`, and reset between tests via
:func:`reset_broadcaster` — our ``alo_app`` fixture creates a fresh
event loop per test, so holding a Redis connection that was bound to a
dead loop would blow up on the next test's first publish.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from redis import asyncio as redis_asyncio

from app.core.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    from redis.asyncio.client import Redis

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON encoding — Chatwoot's ActiveSupport::JSON emits ISO-8601 for
# DateTime and plain strings for UUIDs. Match that so the wire payload is
# diff-identical to what the Ruby app would ship for the same model.
# ---------------------------------------------------------------------------
def _default_json(o: Any) -> Any:
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, UUID):
        return str(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def encode_envelope(event: str, data: dict[str, Any]) -> bytes:
    """Serialize the ``{event, data}`` envelope for PUBLISH.

    Extracted so the WebSocket handler (4b.2) and any test helper can
    reuse the exact encoding.
    """
    return json.dumps({"event": event, "data": data}, default=_default_json).encode("utf-8")


# ---------------------------------------------------------------------------
# Broadcaster
# ---------------------------------------------------------------------------
class RealtimeBroadcaster:
    """Thin async wrapper around ``redis.asyncio.Redis``.

    We deliberately keep the interface small — one ``publish`` call that
    fans out over a list of channels, plus an escape hatch for the WS
    subscribe-pump to reach the underlying client.
    """

    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    @classmethod
    def from_url(cls, url: str) -> "RealtimeBroadcaster":
        # ``decode_responses=False`` so the pub/sub payloads are raw bytes
        # on both sides — the WS subscriber decodes once on receipt.
        client = redis_asyncio.from_url(url, decode_responses=False)
        return cls(client)

    async def publish(
        self,
        channels: "list[str] | set[str] | tuple[str, ...]",
        event: str,
        data: dict[str, Any],
    ) -> int:
        """Publish ``{event, data}`` to each unique, non-empty channel.

        Returns the number of channels actually published to — handy for
        tests that want to assert "one broadcast per token". Empty
        ``channels`` is a no-op (mirrors ``ActionCableBroadcastJob``'s
        ``return if members.blank?`` early out).
        """
        unique = {c for c in channels if c}
        if not unique:
            return 0
        envelope = encode_envelope(event, data)
        async with self._redis.pipeline(transaction=False) as pipe:
            for ch in unique:
                pipe.publish(ch, envelope)
            await pipe.execute()
        return len(unique)

    async def close(self) -> None:
        """Close the underlying Redis connection pool."""
        try:
            await self._redis.aclose()
        except Exception:  # pragma: no cover - best-effort shutdown
            log.exception("realtime.broadcaster.close failed")

    @property
    def redis(self) -> "Redis":
        """Expose the underlying client for the ``/cable`` subscribe pump."""
        return self._redis


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_broadcaster: RealtimeBroadcaster | None = None


async def get_broadcaster() -> RealtimeBroadcaster:
    """Return the process-wide :class:`RealtimeBroadcaster`.

    Lazily instantiates on first call using ``settings.redis_url``.
    Safe to call from any async context.
    """
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = RealtimeBroadcaster.from_url(get_settings().redis_url)
    return _broadcaster


def set_broadcaster(broadcaster: RealtimeBroadcaster | None) -> None:
    """Install a pre-built broadcaster — intended for tests."""
    global _broadcaster
    _broadcaster = broadcaster


async def reset_broadcaster() -> None:
    """Close + forget the singleton. Called from the app lifespan's
    shutdown branch so the per-test fixture doesn't leak a Redis client
    bound to the previous event loop.
    """
    global _broadcaster
    if _broadcaster is not None:
        await _broadcaster.close()
    _broadcaster = None


__all__ = [
    "RealtimeBroadcaster",
    "encode_envelope",
    "get_broadcaster",
    "reset_broadcaster",
    "set_broadcaster",
]
