"""AutoAssignmentHandler — runs round-robin on the right hooks.

Ported from:
  reference/chatwoot/app/models/concerns/auto_assignment_handler.rb
  reference/chatwoot/app/models/concerns/assignment_handler.rb
  (the ``find_assignee_from_team`` half — we collapse them here so the
  service layer has one entry point per trigger.)

Trigger surface (mirrors Rails ``after_save :run_auto_assignment``):
  * After a conversation is created without an explicit assignee —
    ``create_conversation`` calls us once the row is persisted.
  * After a team change in ``update_team`` — when the new team allows
    auto-assign and the assignee was cleared (or never set), we
    pick from the team∩inbox-member intersection.
  * After ``toggle_status`` flips the conversation back to ``open`` —
    Rails' v1 path doesn't strictly require this (the ``open?``
    branch is v2-only), but we mirror it because most Chatwoot
    deployments expect a re-opened conversation to land back on a
    rotating agent if the previous assignee left the inbox.

Allowed-agent computation (Rails ``run_auto_assignment``):
  * If the conversation has a team -> ``inbox.member_ids ∩ team.member_ids``
    (filtered by ``team.allow_auto_assign`` — falsey ⇒ no candidates).
  * Otherwise -> all inbox members.

Deferred:
  * V2 capacity-rebalance (``AssignmentJob.perform_later``) — Phase 7.
  * Online-agent intersection — needs ``OnlineStatusTracker``.
  * Inbox-level enforcement of admin-only members — InboxBuilder
    seeds members with the admin's row, which already gates this
    sufficiently for the round-robin pool.
"""

from __future__ import annotations

import logging

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.realtime import get_broadcaster
from app.domains.auto_assignment.agent_assignment import perform as _agent_assignment_perform
from app.domains.conversations.events import (
    ASSIGNEE_CHANGED,
    CONVERSATION_UPDATED,
    dispatcher,
)
from app.domains.conversations.models import Conversation
from app.domains.inboxes.models import Inbox, InboxMember
from app.domains.teams.models import Team, TeamMember

log = logging.getLogger(__name__)


async def _allowed_agent_ids(
    session: AsyncSession, *, conversation: Conversation
) -> list[int]:
    """Compute the candidate user_ids for round-robin.

    Mirrors the branch in ``AutoAssignmentHandler#run_auto_assignment``:
    team-scoped when a team is set + allows auto-assign, otherwise the
    full inbox member set.
    """
    member_ids = list(
        (
            await session.exec(
                select(InboxMember.user_id).where(
                    InboxMember.inbox_id == conversation.inbox_id
                )
            )
        ).all()
    )
    if not member_ids:
        return []

    if conversation.team_id is not None:
        team = await session.get(Team, conversation.team_id)
        if team is None or not team.allow_auto_assign:
            return []
        team_member_ids = list(
            (
                await session.exec(
                    select(TeamMember.user_id).where(
                        TeamMember.team_id == conversation.team_id
                    )
                )
            ).all()
        )
        # ``inbox.member_ids_with_assignment_capacity & team.members.ids``
        return [int(uid) for uid in member_ids if uid in set(team_member_ids)]
    return [int(uid) for uid in member_ids]


async def _should_run(
    session: AsyncSession, *, conversation: Conversation
) -> bool:
    """Mirror ``should_run_auto_assignment?``.

    v1 branch only: skip when the inbox has auto-assign disabled, or
    when the assignee is already an inbox member.
    """
    if conversation.inbox_id is None:
        return False
    inbox = await session.get(Inbox, conversation.inbox_id)
    if inbox is None or not inbox.enable_auto_assignment:
        return False
    if conversation.assignee_id is None:
        return True
    # Has an assignee — only re-run if they're no longer in the inbox.
    is_member = (
        await session.exec(
            select(InboxMember.id).where(
                InboxMember.inbox_id == conversation.inbox_id,
                InboxMember.user_id == conversation.assignee_id,
            )
        )
    ).first()
    return is_member is None


async def maybe_run_auto_assignment(
    session: AsyncSession, *, conversation: Conversation
) -> int | None:
    """Top-level entry point — runs auto-assignment if eligible.

    Returns the chosen user_id (or ``None`` when no agent was picked).
    On a successful pick, dispatches ``ASSIGNEE_CHANGED`` +
    ``CONVERSATION_UPDATED`` so the realtime layer + listeners see the
    change. Activity-row insert is intentionally skipped — Rails fires
    it from ``AssignmentHandler#process_assignment_activities`` only
    when ``Current.user`` is set; auto-assignment runs without an actor
    so the row would render with a blank user_name and Rails drops it
    via ``activity_message_owner`` returning nil. We match that
    behaviour by simply not emitting the row.
    """
    if not await _should_run(session, conversation=conversation):
        return None
    candidates = await _allowed_agent_ids(
        session, conversation=conversation
    )
    if not candidates:
        return None

    prev_id = conversation.assignee_id
    try:
        broadcaster = await get_broadcaster()
        chosen = await _agent_assignment_perform(
            broadcaster.redis,
            session,
            conversation=conversation,
            allowed_agent_ids=candidates,
        )
    except Exception:
        # A Redis flake or schema drift must not break the request.
        log.exception("auto_assignment.error conversation_id=%s", conversation.id)
        return None

    if chosen is None or chosen == prev_id:
        return chosen

    await dispatcher.dispatch(
        session, ASSIGNEE_CHANGED, conversation=conversation
    )
    await dispatcher.dispatch(
        session,
        CONVERSATION_UPDATED,
        conversation=conversation,
        changed_attributes={"assignee_id": [prev_id, chosen]},
    )
    return chosen


__all__ = ["maybe_run_auto_assignment"]
