"""NotificationListener — creates Notification rows on dispatcher events.

Ports:
  reference/chatwoot/app/listeners/notification_listener.rb

Subscribes to three dispatcher events for Phase v2.5:

  * ``conversation.created`` → ``conversation_creation`` for every
    inbox member except the performer.
  * ``assignee.changed``     → ``conversation_assignment`` for the
    new assignee, skipping when the assignee performed the change
    themselves.
  * ``message.created``      → ``assigned_conversation_new_message``
    for the conversation's assignee when the message is incoming
    AND the assignee isn't the sender (defensive — Contact senders
    can never match an assignee, but the check costs nothing).

After each insert, also fires an ActionCable broadcast to the
assignee's account stream so the bell badge updates without the
client polling. Failure-isolated per row so one bad insert doesn't
sink the others.

Skipped:

  * ``conversation_mention``     — needs a mention parser on message
    content; deferred until we ship the mention service.
  * SLA-missed notifications     — SLA not ported (PLAN.parity-review §7).
  * Push / email side-effects    — Chatwoot delivers notifications via
    Firebase + ActionMailer here; the in-app surface ships standalone
    and the push/email worker is a future ARQ job.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.realtime import get_broadcaster
from app.domains.conversations import events as ev
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    Conversation,
    Message,
)
from app.domains.inboxes.models import InboxMember
from app.domains.notifications.mailer import enqueue_notification_email
from app.domains.notifications.models import (
    NOTIFICATION_TYPE_ASSIGNED_CONVERSATION_NEW_MESSAGE,
    NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT,
    NOTIFICATION_TYPE_CONVERSATION_CREATION,
    Notification,
)
from app.domains.notifications.presenters import present_notification
from app.domains.notifications.push import enqueue_notification_push
from app.domains.notifications.service import create_notification
from app.domains.users.models import User

log = logging.getLogger(__name__)


async def fan_out_to_notifications(
    session: AsyncSession, event_name: str, **payload: Any
) -> None:
    """Entry point called from the conversations dispatcher."""
    try:
        if event_name == ev.CONVERSATION_CREATED:
            await _on_conversation_created(session, payload)
        elif event_name == ev.ASSIGNEE_CHANGED:
            await _on_assignee_changed(session, payload)
        elif event_name == ev.MESSAGE_CREATED:
            await _on_message_created(session, payload)
    except Exception:
        log.exception("notifications.listener.error event=%s", event_name)


# ---------------------------------------------------------------------------
# Per-event handlers
# ---------------------------------------------------------------------------
async def _on_conversation_created(
    session: AsyncSession, payload: dict[str, Any]
) -> None:
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return
    performer_id = _performer_id(payload)
    member_ids = await _inbox_member_ids(session, conversation.inbox_id)
    for uid in member_ids:
        if uid == performer_id:
            continue
        notification = await create_notification(
            session,
            account_id=conversation.account_id,  # type: ignore[arg-type]
            user_id=uid,
            notification_type=NOTIFICATION_TYPE_CONVERSATION_CREATION,
            primary_actor_type="Conversation",
            primary_actor_id=conversation.id,  # type: ignore[arg-type]
        )
        await _broadcast_created(session, notification, conversation)


async def _on_assignee_changed(
    session: AsyncSession, payload: dict[str, Any]
) -> None:
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return
    assignee_id = conversation.assignee_id
    if assignee_id is None:
        return
    performer_id = _performer_id(payload)
    if performer_id == assignee_id:
        # User assigned themselves — they already know.
        return
    notification = await create_notification(
        session,
        account_id=conversation.account_id,  # type: ignore[arg-type]
        user_id=assignee_id,
        notification_type=NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT,
        primary_actor_type="Conversation",
        primary_actor_id=conversation.id,  # type: ignore[arg-type]
    )
    await _broadcast_created(session, notification, conversation)


async def _on_message_created(
    session: AsyncSession, payload: dict[str, Any]
) -> None:
    message = payload.get("message")
    if not isinstance(message, Message):
        return
    if message.message_type != MESSAGE_TYPE_INCOMING:
        return
    if message.private:
        return
    conversation = message.conversation
    if not isinstance(conversation, Conversation):
        return
    assignee_id = conversation.assignee_id
    if assignee_id is None:
        return
    # Defensive: contact senders won't match an assignee anyway, but
    # the explicit check keeps the rule visible.
    if message.sender_type == "User" and message.sender_id == assignee_id:
        return
    notification = await create_notification(
        session,
        account_id=conversation.account_id,  # type: ignore[arg-type]
        user_id=assignee_id,
        notification_type=NOTIFICATION_TYPE_ASSIGNED_CONVERSATION_NEW_MESSAGE,
        primary_actor_type="Conversation",
        primary_actor_id=conversation.id,  # type: ignore[arg-type]
        secondary_actor_type="Message",
        secondary_actor_id=message.id,
    )
    await _broadcast_created(session, notification, conversation)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _inbox_member_ids(
    session: AsyncSession, inbox_id: int | None
) -> list[int]:
    if inbox_id is None:
        return []
    stmt = select(InboxMember.user_id).where(InboxMember.inbox_id == inbox_id)
    return [
        uid
        for uid in (await session.exec(stmt)).all()
        if uid is not None
    ]


def _performer_id(payload: dict[str, Any]) -> int | None:
    """Pull the acting user id out of the dispatcher payload.

    The dispatcher passes ``performer`` keyed on the current user
    when there is one (HTTP request flow). Background-job dispatches
    leave it ``None`` and we don't suppress notifications then —
    safer to over-notify than to miss the assignee.
    """
    performer = payload.get("performer")
    return getattr(performer, "id", None)


async def _broadcast_created(
    session: AsyncSession,
    notification: Notification,
    conversation: Conversation,
) -> None:
    """Push a ``notification.created`` event to the recipient's cable
    channel so the dashboard bell badge updates live.

    The cable layer subscribes on the user's ``pubsub_token`` (see
    ``app/domains/conversations/listeners.py``'s broadcaster pattern);
    we publish to that single channel rather than an account-wide one
    so an admin watching multiple accounts doesn't get cross-talk."""
    # Email + web-push side-effects — best-effort ARQ enqueues that run
    # regardless of whether the recipient has a live cable connection for the
    # badge (each send task re-checks the user's own subscription preference).
    if notification.id is not None:
        await enqueue_notification_email(notification.id)
        await enqueue_notification_push(notification.id)

    user = await session.get(User, notification.user_id)
    if user is None or not user.pubsub_token:
        return
    broadcaster = await get_broadcaster()
    body = present_notification(notification, primary_actor=conversation)
    try:
        await broadcaster.publish(
            [user.pubsub_token],
            "notification.created",
            {
                "account_id": notification.account_id,
                "notification": body,
            },
        )
    except Exception:
        log.exception(
            "notifications.broadcast.error notification_id=%s",
            notification.id,
        )


__all__ = ["fan_out_to_notifications"]
