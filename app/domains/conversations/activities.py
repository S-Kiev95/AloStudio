"""Activity-message generation — the ``message_type=activity`` rows
the dashboard renders as grey timeline entries ("Conversation was
marked resolved by Alice", "Bob added urgent label", etc).

Ported from:
  reference/chatwoot/app/models/concerns/activity_message_handler.rb
  reference/chatwoot/app/models/concerns/{assignee,priority,label,team}_activity_message_handler.rb
  reference/chatwoot/config/locales/en.yml (``conversations.activity.*``)
  reference/chatwoot/app/jobs/conversations/activity_message_job.rb

The Ruby side hooks into ActiveRecord ``after_update_commit`` callbacks
(``ActivityMessageHandler#create_activity``) and queues an
``ActivityMessageJob`` per change. Async Sidekiq write decouples the
controller response from the activity insert.

Our port collapses the job indirection: the service-layer mutation
calls :func:`create_activity_message` directly inside the same DB
transaction. The activity row is written, then the dispatcher fires
``MESSAGE_CREATED`` so the realtime broadcaster fans it out — same
end-state, fewer moving parts (no Sidekiq equivalent yet, see
``app/core/jobs.py`` arq plans for Phase 5).

Deferred to later phases (mirrors ``ActivityMessageHandler``):
  * ``automation_status_change_activity_content`` (AutomationRule
    branches) — Phase 6.
  * ``sla_change`` activity — Phase 9 (SLA model not yet ported).
  * Captain/AgentBot resolution branches — Phase 8.

Locale strings are hard-coded English. When we ship i18n we'll move
these into ``app/locales/en.json`` and key them by the same path
(``conversations.activity.status.resolved`` etc) — until then keeping
them inline avoids a layer of indirection that would obscure parity.
"""

from __future__ import annotations

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.events import MESSAGE_CREATED, dispatcher
from app.domains.conversations.models import (
    CONTENT_TYPE_TEXT,
    MESSAGE_TYPE_ACTIVITY,
    Conversation,
    Message,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Content generators — one per ActivityMessageHandler concern
# ---------------------------------------------------------------------------
# Status (``ActivityMessageHandler#user_status_change_activity_content``)
_STATUS_TEMPLATES: dict[str, str] = {
    "resolved": "Conversation was marked resolved by {user_name}",
    "open": "Conversation was reopened by {user_name}",
    "pending": "Conversation was marked as pending by {user_name}",
    "snoozed": "Conversation was snoozed by {user_name}",
}


def status_change_activity_content(
    *, status: str, user_name: str | None
) -> str | None:
    """Mirror ``user_status_change_activity_content``.

    Without a ``user_name`` (e.g. system-triggered status change with
    no Current.user) we drop the activity. The Rails branch for
    ``contact_resolved`` / ``auto_resolved_*`` lands when we wire
    auto-resolution in Phase 6.
    """
    if not user_name:
        return None
    template = _STATUS_TEMPLATES.get(status)
    if template is None:
        return None
    return template.format(user_name=user_name)


# Priority (``PriorityActivityMessageHandler#build_priority_change_content``)
def priority_change_activity_content(
    *,
    user_name: str | None,
    old_priority: str | None,
    new_priority: str | None,
) -> str | None:
    """Mirror ``build_priority_change_content``.

    Three shapes:
      * old + new   ->  "%{user_name} changed the priority from %{old} to %{new}"
      * none + new  ->  "%{user_name} set the priority to %{new}"
      * old + none  ->  "%{user_name} removed the priority"

    Returns None if neither side is set (no-op change) or no user.
    """
    if not user_name:
        return None
    has_old = bool(old_priority)
    has_new = bool(new_priority)
    if has_old and has_new:
        return (
            f"{user_name} changed the priority from {old_priority} to {new_priority}"
        )
    if has_new:
        return f"{user_name} set the priority to {new_priority}"
    if has_old:
        return f"{user_name} removed the priority"
    return None


# Assignee (``AssigneeActivityMessageHandler#generate_assignee_change_activity_content``)
def assignee_change_activity_content(
    *,
    user_name: str | None,
    assignee_name: str | None,
    self_assigned: bool,
    is_assigned: bool,
) -> str | None:
    """Mirror ``generate_assignee_change_activity_content``.

    Three shapes:
      * is_assigned and self_assigned -> "%{user_name} self-assigned this conversation"
      * is_assigned                   -> "Assigned to %{assignee_name} by %{user_name}"
      * not is_assigned               -> "Conversation unassigned by %{user_name}"
    """
    if not user_name:
        return None
    if is_assigned and self_assigned:
        return f"{user_name} self-assigned this conversation"
    if is_assigned:
        return f"Assigned to {assignee_name or ''} by {user_name}"
    return f"Conversation unassigned by {user_name}"


# Team (``TeamActivityMessageHandler#create_team_change_activity``)
def team_change_activity_content(
    *,
    user_name: str | None,
    new_team_name: str | None,
    previous_team_name: str | None,
    assignee_name: str | None,
    assignee_changed: bool,
) -> str | None:
    """Mirror ``create_team_change_activity`` + ``generate_team_change_activity_key``.

    Four shapes:
      * has new_team and assignee_changed and assignee_name ->
          "Assigned to %{assignee_name} via %{team_name} by %{user_name}"
      * has new_team -> "Assigned to %{team_name} by %{user_name}"
      * no new_team  -> "Unassigned from %{team_name} by %{user_name}"
        (using ``previous_team_name`` because the team_id has been cleared)
    """
    if not user_name:
        return None
    if new_team_name:
        if assignee_changed and assignee_name:
            return (
                f"Assigned to {assignee_name} via {new_team_name} "
                f"by {user_name}"
            )
        return f"Assigned to {new_team_name} by {user_name}"
    # Removed branch
    name = previous_team_name or ""
    return f"Unassigned from {name} by {user_name}"


# Labels (``LabelActivityMessageHandler#create_label_change_activity``)
def label_change_activity_content(
    *,
    user_name: str | None,
    change_type: str,
    labels: list[str],
) -> str | None:
    """Mirror ``create_label_change_activity``.

    ``change_type`` is ``'added'`` or ``'removed'``. ``labels`` is the
    diff list — empty diff drops the activity (parity with Rails
    ``return unless labels.size.positive?``).
    """
    if not user_name or not labels:
        return None
    if change_type not in ("added", "removed"):
        return None
    return f"{user_name} {change_type} {', '.join(labels)}"


# Mute (``ActivityMessageHandler#create_mute_change_activity``)
def mute_change_activity_content(
    *, user_name: str | None, change_type: str
) -> str | None:
    """Mirror ``create_mute_change_activity``.

    ``change_type`` is ``'muted'`` or ``'unmuted'``. Rails drops the
    activity when ``Current.user`` is nil — same here.
    """
    if not user_name:
        return None
    if change_type == "muted":
        return f"{user_name} has muted the conversation"
    if change_type == "unmuted":
        return f"{user_name} has unmuted the conversation"
    return None


# ---------------------------------------------------------------------------
# Activity row creator
# ---------------------------------------------------------------------------
async def create_activity_message(
    session: AsyncSession,
    *,
    conversation: Conversation,
    content: str,
) -> Message | None:
    """Insert the activity Message + dispatch ``MESSAGE_CREATED``.

    Mirrors ``ActivityMessageJob#perform``:

        conversation.messages.create!(account_id:, inbox_id:,
                                      message_type: :activity,
                                      content:)

    Plus the Message after-create callbacks that matter for an activity
    row — there are none in 4b that don't also apply to a normal
    incoming/outgoing message, but activity rows DO trigger
    ``MESSAGE_CREATED`` via :class:`ActionCableListener` so the
    timeline updates in real time.

    Returns the inserted Message, or ``None`` if ``content`` is empty.
    """
    if not content:
        return None
    msg = Message(
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        sender_type=None,
        sender_id=None,
        message_type=MESSAGE_TYPE_ACTIVITY,
        content_type=CONTENT_TYPE_TEXT,
        content=content,
        # Activity rows aren't "private" or "outgoing" — leave the
        # boolean defaults at False / None.
        private=False,
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)
    # Stash a None resolved sender so the presenter doesn't try to look
    # up sender_id; mirrors the Rails branch where activity messages
    # render without a sender block.
    msg._resolved_sender = None

    await dispatcher.dispatch(session, MESSAGE_CREATED, message=msg)
    return msg


__all__ = [
    "assignee_change_activity_content",
    "create_activity_message",
    "label_change_activity_content",
    "mute_change_activity_content",
    "priority_change_activity_content",
    "status_change_activity_content",
    "team_change_activity_content",
]
