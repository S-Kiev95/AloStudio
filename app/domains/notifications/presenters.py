"""Wire-shape presenters for Notification + NotificationSetting."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.conversations.models import (
    Conversation,
    conversation_priority_to_str,
    conversation_status_to_str,
)
from app.domains.notifications.models import (
    Notification,
    NotificationSetting,
    notification_type_to_str,
)


def _unix(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    return int(dt.timestamp())


def _present_conversation_actor(conv: Conversation) -> dict[str, Any]:
    """Slim ``Conversation`` block embedded inside a notification.

    Mirrors ``Conversation#push_event_data`` upstream (subset): the
    notification panel needs enough to route the user to the
    conversation and show context — id / display_id / status /
    inbox_id / contact_id / assignee_id.
    """
    return {
        "id": conv.id,
        "display_id": conv.display_id,
        "account_id": conv.account_id,
        "inbox_id": conv.inbox_id,
        "contact_id": conv.contact_id,
        "assignee_id": conv.assignee_id,
        "status": conversation_status_to_str(conv.status),
        "priority": conversation_priority_to_str(conv.priority),
        "uuid": str(conv.uuid) if conv.uuid is not None else None,
    }


def present_notification(
    notification: Notification,
    *,
    primary_actor: Conversation | None = None,
) -> dict[str, Any]:
    """One notification row.

    ``primary_actor`` is passed in pre-loaded so the presenter stays
    free of DB access — the router batches the loads.
    """
    body: dict[str, Any] = {
        "id": notification.id,
        "notification_type": notification_type_to_str(
            notification.notification_type
        ),
        "primary_actor_type": notification.primary_actor_type,
        "primary_actor_id": notification.primary_actor_id,
        "secondary_actor_type": notification.secondary_actor_type,
        "secondary_actor_id": notification.secondary_actor_id,
        "read_at": _unix(notification.read_at),
        "snoozed_until": _unix(notification.snoozed_until),
        "last_activity_at": _unix(notification.last_activity_at),
        "created_at": _unix(notification.created_at),
        "account_id": notification.account_id,
        "user_id": notification.user_id,
        "meta": notification.meta or {},
    }
    if primary_actor is not None:
        body["primary_actor"] = _present_conversation_actor(primary_actor)
    return body


def present_notifications_index(
    notifications: list[Notification],
    *,
    primary_actor_by_key: dict[tuple[str, int], Conversation],
    count: int,
    unread_count: int,
    current_page: int,
) -> dict[str, Any]:
    """``GET /notifications`` envelope."""
    return {
        "meta": {
            "count": count,
            "unread_count": unread_count,
            "current_page": current_page,
        },
        "payload": [
            present_notification(
                n,
                primary_actor=primary_actor_by_key.get(
                    (n.primary_actor_type, n.primary_actor_id)
                ),
            )
            for n in notifications
        ],
    }


def present_notification_settings(s: NotificationSetting) -> dict[str, Any]:
    """``GET /notification_settings`` envelope.

    The Rails frontend reads ``selected_email_flags`` /
    ``selected_push_flags`` as arrays of type-name strings.
    """
    return {
        "id": s.id,
        "account_id": s.account_id,
        "user_id": s.user_id,
        "selected_email_flags": list(s.email_subscriptions or []),
        "selected_push_flags": list(s.push_subscriptions or []),
    }


__all__ = [
    "present_notification",
    "present_notification_settings",
    "present_notifications_index",
]
