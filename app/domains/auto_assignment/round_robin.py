"""Inbox round-robin queue.

Ported from:
  reference/chatwoot/app/services/auto_assignment/inbox_round_robin_service.rb
  reference/chatwoot/lib/redis/redis_keys.rb (ROUND_ROBIN_AGENTS key)

Maintains a Redis list per inbox where each list element is a user_id.
Picking an assignee pops the head, the popped id gets pushed back to
the tail — classic FIFO round-robin.

The Rails service uses ``Redis::Alfred`` (a thin DSL on top of redis-rb)
plus three after-commit callbacks on InboxMember to keep the list in
sync with membership. We collapse the callback path: the
``available_agent`` entry point auto-rebuilds the queue when it
detects a drift from current inbox-members (Rails' ``validate_queue?``
fallback). That gives us correct behaviour without porting Rails'
``InboxMember`` lifecycle hooks — same outcome, fewer moving parts.

Key format mirrors Chatwoot:
  ``ROUND_ROBIN_AGENTS:<inbox_id>``  (decimal id, no leading zeros).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.inboxes.models import InboxMember

if TYPE_CHECKING:  # pragma: no cover
    from redis.asyncio import Redis


def round_robin_key(inbox_id: int) -> str:
    """Mirror ``format(Redis::Alfred::ROUND_ROBIN_AGENTS, inbox_id: id)``."""
    return f"ROUND_ROBIN_AGENTS:{inbox_id}"


async def _queue(redis: Redis, inbox_id: int) -> list[int]:
    """Read the full queue as a list of ints (Redis returns bytes)."""
    raw = await redis.lrange(round_robin_key(inbox_id), 0, -1)
    out: list[int] = []
    for item in raw:
        if isinstance(item, (bytes, bytearray)):
            item = item.decode("utf-8")
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


async def _inbox_member_user_ids(
    session: AsyncSession, inbox_id: int
) -> list[int]:
    rows = (
        await session.exec(
            select(InboxMember.user_id).where(InboxMember.inbox_id == inbox_id)
        )
    ).all()
    return [int(r) for r in rows if r is not None]


async def _reset_queue(
    redis: Redis, session: AsyncSession, inbox_id: int
) -> list[int]:
    """Mirror ``reset_queue`` — drop the list, then ``lpush`` every member.

    Rails ``add_agent_to_queue(inbox_members.map(&:user_id))`` relies on
    redis-rb's variadic ``lpush(key, *values)``. We do the same here.
    Returns the rebuilt queue (head-first order matches Rails: the last
    pushed user_id is at the front).
    """
    key = round_robin_key(inbox_id)
    member_ids = await _inbox_member_user_ids(session, inbox_id)
    await redis.delete(key)
    if member_ids:
        # ``lpush key v1 v2 v3`` results in [v3, v2, v1] — head is the
        # last argument. We pass the ids in their natural order and
        # accept that flavour because Rails does the same.
        await redis.lpush(key, *(str(uid) for uid in member_ids))
    return list(reversed(member_ids))


async def _validate_queue(
    redis: Redis, session: AsyncSession, inbox_id: int
) -> bool:
    """Mirror ``validate_queue?`` — sorted member ids match the queue."""
    queue = sorted(await _queue(redis, inbox_id))
    members = sorted(await _inbox_member_user_ids(session, inbox_id))
    return queue == members


async def available_agent(
    redis: Redis,
    session: AsyncSession,
    *,
    inbox_id: int,
    allowed_agent_ids: list[int],
) -> int | None:
    """Pop the next round-robin assignee from ``allowed_agent_ids``.

    Mirrors ``InboxRoundRobinService#available_agent``:

      reset_queue unless validate_queue?
      user_id = queue.intersection(allowed_agent_ids).pop
      pop_push_to_queue(user_id)
      user_id

    Returns the picked user_id or ``None`` when the intersection is
    empty (no eligible agent).
    """
    if not allowed_agent_ids:
        return None
    if not await _validate_queue(redis, session, inbox_id):
        await _reset_queue(redis, session, inbox_id)

    queue = await _queue(redis, inbox_id)
    allowed = set(allowed_agent_ids)
    # ``queue.intersection(allowed_agent_ids).pop`` in Ruby pops the
    # LAST matching element of the resulting array (Array#pop). We
    # iterate the queue from the tail so the rotation behaves the
    # same — the agent at the back of the queue is selected next.
    chosen: int | None = None
    for uid in reversed(queue):
        if uid in allowed:
            chosen = uid
            break
    if chosen is None:
        return None

    key = round_robin_key(inbox_id)
    # ``pop_push_to_queue``: lrem then lpush — sends the picked agent
    # back to the head so the next pass picks someone else.
    await redis.lrem(key, 0, str(chosen))
    await redis.lpush(key, str(chosen))
    return chosen


__all__ = [
    "available_agent",
    "round_robin_key",
]
