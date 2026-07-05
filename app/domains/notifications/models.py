"""Notification + NotificationSetting.

Ports:
  reference/chatwoot/app/models/notification.rb
  reference/chatwoot/app/models/notification_setting.rb

Wire-shape notes:

* Chatwoot stores ``notification_type`` as an integer enum +
  ``primary_actor_type`` / ``primary_actor_id`` (polymorphic). We
  mirror exactly so the API body matches.
* Settings store ``email_flags`` / ``push_flags`` as bit-packed
  integers on Chatwoot. We swap that for two JSONB arrays of
  type-name strings — cleaner in Python, same observable behaviour
  on the wire when the API surfaces ``selected_email_flags`` /
  ``selected_push_flags`` lists.

Scope (Phase v2.5):

* ``conversation_creation``       — new conversation lands in an inbox I'm a member of
* ``conversation_assignment``     — a conversation gets assigned to me
* ``assigned_conversation_new_message`` — new incoming message on a conversation assigned to me

Deferred:

* ``conversation_mention``        — needs a mention parser on messages
* SLA-missed notifications        — SLA not ported yet (PLAN.parity-review §7)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# --- notification_type int enum (Chatwoot-parity ordering) -------------
NOTIFICATION_TYPE_CONVERSATION_CREATION = 1
NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT = 2
NOTIFICATION_TYPE_ASSIGNED_CONVERSATION_NEW_MESSAGE = 3
NOTIFICATION_TYPE_CONVERSATION_MENTION = 4
NOTIFICATION_TYPE_PARTICIPATING_CONVERSATION_NEW_MESSAGE = 5
NOTIFICATION_TYPE_SLA_MISSED_FIRST_RESPONSE = 6
NOTIFICATION_TYPE_SLA_MISSED_NEXT_RESPONSE = 7
NOTIFICATION_TYPE_SLA_MISSED_RESOLUTION = 8

_NOTIFICATION_TYPE_INT_TO_STR: dict[int, str] = {
    NOTIFICATION_TYPE_CONVERSATION_CREATION: "conversation_creation",
    NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT: "conversation_assignment",
    NOTIFICATION_TYPE_ASSIGNED_CONVERSATION_NEW_MESSAGE: "assigned_conversation_new_message",
    NOTIFICATION_TYPE_CONVERSATION_MENTION: "conversation_mention",
    NOTIFICATION_TYPE_PARTICIPATING_CONVERSATION_NEW_MESSAGE: "participating_conversation_new_message",
    NOTIFICATION_TYPE_SLA_MISSED_FIRST_RESPONSE: "sla_missed_first_response",
    NOTIFICATION_TYPE_SLA_MISSED_NEXT_RESPONSE: "sla_missed_next_response",
    NOTIFICATION_TYPE_SLA_MISSED_RESOLUTION: "sla_missed_resolution",
}
_NOTIFICATION_TYPE_STR_TO_INT: dict[str, int] = {
    v: k for k, v in _NOTIFICATION_TYPE_INT_TO_STR.items()
}


def notification_type_to_str(value: int | None) -> str:
    if value is None:
        return ""
    return _NOTIFICATION_TYPE_INT_TO_STR.get(value, "")


def notification_type_from_str(value: str) -> int:
    if value not in _NOTIFICATION_TYPE_STR_TO_INT:
        raise ValueError(f"unknown notification_type: {value!r}")
    return _NOTIFICATION_TYPE_STR_TO_INT[value]


# --- Notification ------------------------------------------------------
class Notification(TimestampMixin, table=True):
    __tablename__ = "notifications"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    user_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )

    notification_type: int = Field(
        sa_column=Column(Integer, nullable=False),
    )

    # Polymorphic primary actor (today only "Conversation" — see
    # ``Notification::PRIMARY_ACTORS`` upstream).
    primary_actor_type: str = Field(
        sa_column=Column(String, nullable=False),
    )
    primary_actor_id: int = Field(
        sa_column=Column(BigInteger, nullable=False),
    )

    # Polymorphic secondary actor (e.g. the Message that triggered an
    # ``assigned_conversation_new_message``).
    secondary_actor_type: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    secondary_actor_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )

    read_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=False), nullable=True)
    )
    snoozed_until: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=False), nullable=True)
    )
    last_activity_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=False), nullable=True, index=True),
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=True, server_default="{}"),
    )


# --- NotificationSetting ----------------------------------------------
class NotificationSetting(TimestampMixin, table=True):
    __tablename__ = "notification_settings"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "user_id", name="by_account_user"
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    user_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # Two JSONB arrays of notification-type-strings the user is
    # subscribed to. Cleaner than Chatwoot's bit-packed integers
    # while preserving the same observable behaviour.
    email_subscriptions: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, server_default="[]"),
    )
    push_subscriptions: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, server_default="[]"),
    )


# ---------------------------------------------------------------------------
# NotificationSubscription — a registered browser Push API endpoint
# ---------------------------------------------------------------------------
NOTIFICATION_SUBSCRIPTION_BROWSER_PUSH = 1
NOTIFICATION_SUBSCRIPTION_FCM = 2


class NotificationSubscription(TimestampMixin, table=True):
    """A push endpoint the user's browser registered (RFC 8291 web push).

    Ported from ``reference/chatwoot/app/models/notification_subscription.rb``.
    ``identifier`` is the (unique) push endpoint URL; ``subscription_attributes``
    holds the full browser ``PushSubscription`` JSON
    (``{endpoint, keys: {p256dh, auth}}``). We only implement
    ``browser_push`` (type 1); FCM (2) stays unported.
    """

    __tablename__ = "notification_subscriptions"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    user_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    identifier: str = Field(
        sa_column=Column(String, nullable=False, unique=True),
    )
    subscription_type: int = Field(
        default=NOTIFICATION_SUBSCRIPTION_BROWSER_PUSH,
        sa_column=Column(
            Integer,
            nullable=False,
            server_default=str(NOTIFICATION_SUBSCRIPTION_BROWSER_PUSH),
        ),
    )
    subscription_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )


__all__ = [
    "NOTIFICATION_SUBSCRIPTION_BROWSER_PUSH",
    "NOTIFICATION_SUBSCRIPTION_FCM",
    "NOTIFICATION_TYPE_ASSIGNED_CONVERSATION_NEW_MESSAGE",
    "NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT",
    "NOTIFICATION_TYPE_CONVERSATION_CREATION",
    "NOTIFICATION_TYPE_CONVERSATION_MENTION",
    "NOTIFICATION_TYPE_PARTICIPATING_CONVERSATION_NEW_MESSAGE",
    "NOTIFICATION_TYPE_SLA_MISSED_FIRST_RESPONSE",
    "NOTIFICATION_TYPE_SLA_MISSED_NEXT_RESPONSE",
    "NOTIFICATION_TYPE_SLA_MISSED_RESOLUTION",
    "Notification",
    "NotificationSetting",
    "NotificationSubscription",
    "notification_type_from_str",
    "notification_type_to_str",
]
