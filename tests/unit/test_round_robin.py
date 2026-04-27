"""Unit tests for ``app.domains.auto_assignment.round_robin``.

We stub Redis with a tiny in-process implementation of the four list
ops the service uses (``lpush`` / ``lrange`` / ``lrem`` / ``delete``)
and monkey-patch ``_inbox_member_user_ids`` to return a fixed roster.
That keeps the test pure — no DB, no network — while still exercising
the queue rotation and lazy-rebuild semantics that ``InboxRoundRobin
Service`` depends on.

Pinned behaviours:
  * Empty allowed-list returns ``None`` (no rebuild side effect).
  * First call rebuilds the queue from inbox members.
  * Subsequent calls rotate so each agent is picked once before any
    repeats — full round-robin coverage.
  * Membership drift triggers ``reset_queue`` (queue not equal to
    inbox-members set ⇒ rebuild before pick).
  * ``allowed_agent_ids`` intersects the queue: agents not in the
    allow-list are skipped, picked agent moves to the head.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domains.auto_assignment import round_robin

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRedis:
    """Minimal subset of ``redis.asyncio.Redis`` for round-robin tests.

    Lists live in a dict keyed by str; values are str (matching the
    bytes-or-str return of real Redis ``lrange``). All ops are coroutines
    so the round_robin module's ``await`` calls land on real awaitables.
    """

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        items = self.lists.get(key, [])
        if stop == -1:
            stop = len(items) - 1
        return items[start : stop + 1]

    async def lpush(self, key: str, *values: Any) -> int:
        # redis-py: ``lpush key v1 v2`` puts v2 at head, then v1.
        # We mirror that: each value is prepended in order.
        bucket = self.lists.setdefault(key, [])
        for v in values:
            bucket.insert(0, str(v))
        return len(bucket)

    async def lrem(self, key: str, count: int, value: Any) -> int:
        bucket = self.lists.get(key)
        if bucket is None:
            return 0
        target = str(value)
        if count == 0:
            removed = bucket.count(target)
            self.lists[key] = [x for x in bucket if x != target]
            return removed
        # Positive count -> head-to-tail; negative -> tail-to-head. We
        # only need count==0 in production but keep the API honest.
        return 0

    async def delete(self, *keys: str) -> int:
        n = 0
        for k in keys:
            if k in self.lists:
                del self.lists[k]
                n += 1
        return n


def _patch_members(monkeypatch: pytest.MonkeyPatch, members: list[int]) -> None:
    async def _stub(_session: Any, _inbox_id: int) -> list[int]:
        return list(members)

    monkeypatch.setattr(round_robin, "_inbox_member_user_ids", _stub)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_returns_none_when_allowed_empty(monkeypatch) -> None:
    redis = _FakeRedis()
    _patch_members(monkeypatch, [1, 2, 3])
    chosen = await round_robin.available_agent(
        redis,
        session=None,  # type: ignore[arg-type]
        inbox_id=42,
        allowed_agent_ids=[],
    )
    assert chosen is None
    # Empty allow-list short-circuits BEFORE any queue rebuild.
    assert redis.lists == {}


async def test_first_call_rebuilds_queue_from_members(monkeypatch) -> None:
    redis = _FakeRedis()
    _patch_members(monkeypatch, [10, 20, 30])
    chosen = await round_robin.available_agent(
        redis, session=None, inbox_id=7, allowed_agent_ids=[10, 20, 30]  # type: ignore[arg-type]
    )
    # Rebuild ran (queue had been empty → not validate_queue).
    assert chosen in (10, 20, 30)
    # Queue retains all three ids, picked one moved to head.
    queue = redis.lists[round_robin.round_robin_key(7)]
    assert sorted(int(x) for x in queue) == [10, 20, 30]
    assert int(queue[0]) == chosen


async def test_full_rotation_visits_every_agent_once(monkeypatch) -> None:
    redis = _FakeRedis()
    _patch_members(monkeypatch, [1, 2, 3])
    picked: list[int] = []
    for _ in range(3):
        c = await round_robin.available_agent(
            redis, session=None, inbox_id=1, allowed_agent_ids=[1, 2, 3]  # type: ignore[arg-type]
        )
        assert c is not None
        picked.append(c)
    assert sorted(picked) == [1, 2, 3]


async def test_skips_agents_not_in_allowed(monkeypatch) -> None:
    """Mirror the queue.intersection(allowed) step — agents outside the
    allowed_agent_ids list never get chosen even though they sit in
    the inbox queue."""
    redis = _FakeRedis()
    _patch_members(monkeypatch, [1, 2, 3])
    # Only agent 2 is eligible (e.g. only one with team membership).
    chosen = await round_robin.available_agent(
        redis, session=None, inbox_id=1, allowed_agent_ids=[2]  # type: ignore[arg-type]
    )
    assert chosen == 2


async def test_membership_drift_triggers_reset(monkeypatch) -> None:
    """Mirror ``validate_queue?`` — when the stored queue diverges from
    the inbox members the service rebuilds before picking."""
    redis = _FakeRedis()
    # Pre-seed a stale queue with a user that's no longer a member.
    redis.lists[round_robin.round_robin_key(9)] = ["999"]
    _patch_members(monkeypatch, [1, 2])

    chosen = await round_robin.available_agent(
        redis, session=None, inbox_id=9, allowed_agent_ids=[1, 2]  # type: ignore[arg-type]
    )
    assert chosen in (1, 2)
    queue = redis.lists[round_robin.round_robin_key(9)]
    assert "999" not in queue
    assert sorted(int(x) for x in queue) == [1, 2]


async def test_returns_none_when_no_overlap(monkeypatch) -> None:
    redis = _FakeRedis()
    _patch_members(monkeypatch, [1, 2, 3])
    chosen = await round_robin.available_agent(
        redis, session=None, inbox_id=1, allowed_agent_ids=[99]  # type: ignore[arg-type]
    )
    assert chosen is None
