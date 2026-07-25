"""Agent auto-assignment.

Ported from:
  reference/chatwoot/app/services/auto_assignment/agent_assignment_service.rb

Picks the next agent for a conversation via the inbox round-robin
queue, intersected with the caller-supplied ``allowed_agent_ids`` (the
list Rails computes from inbox membership ± team membership ± capacity
filters in :mod:`AutoAssignmentHandler`).

Online-status filtering is deferred — Rails takes the intersection of
``allowed_agent_ids`` with ``OnlineStatusTracker.get_available_users``
to skip offline agents. Until we ship the presence heartbeat (4b.7
stretch / later) we treat every member as eligible, which mirrors the
behaviour of a Chatwoot account whose Redis presence keys have all
expired.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.auto_assignment.round_robin import available_agent
from app.domains.conversations.models import Conversation

if TYPE_CHECKING:  # pragma: no cover
    from redis.asyncio import Redis


async def find_assignee(
    redis: Redis,
    session: AsyncSession,
    *,
    conversation: Conversation,
    allowed_agent_ids: list[int],
) -> int | None:
    """Mirror ``AgentAssignmentService#find_assignee``.

    Without a presence tracker the ``allowed_online_agent_ids``
    intersection collapses to ``allowed_agent_ids`` — see module
    docstring for the deferral.
    """
    if conversation.inbox_id is None or not allowed_agent_ids:
        return None
    return await available_agent(
        redis,
        session,
        inbox_id=conversation.inbox_id,
        allowed_agent_ids=allowed_agent_ids,
    )


async def perform(
    redis: Redis,
    session: AsyncSession,
    *,
    conversation: Conversation,
    allowed_agent_ids: list[int],
) -> int | None:
    """Mirror ``AgentAssignmentService#perform``.

    Picks an assignee + writes it back to the conversation. Returns the
    assigned user_id (or ``None`` if no agent was available). The
    caller is responsible for dispatching events / activity rows —
    we keep this function dependency-free so it's safe to call from
    the various ``run_auto_assignment`` hook sites without an event
    loop reentrancy concern.
    """
    chosen = await find_assignee(
        redis,
        session,
        conversation=conversation,
        allowed_agent_ids=allowed_agent_ids,
    )
    if chosen is None:
        return None
    conversation.assignee_id = chosen
    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)
    return chosen


__all__ = ["find_assignee", "perform"]
