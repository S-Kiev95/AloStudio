"""Webhook — account-configured outbound HTTP receiver.

Ported from:
  reference/chatwoot/app/models/webhook.rb
  reference/chatwoot/db/schema.rb (``webhooks`` table)

The account configures one row per (url, subscriptions[]); the
listener (see :mod:`app.domains.webhooks.listener`) POSTs the standard
Chatwoot webhook envelope to every Webhook whose ``subscriptions``
includes the dispatcher event name.

``webhook_type`` distinguishes account-wide webhooks (the only kind
Phase 8 reads from) from inbox-scoped ones (defer to follow-up — the
schema column is preserved for parity).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func as sa_func
from sqlmodel import Field, SQLModel

from app.core.base_model import TimestampMixin

# v2.9 — receiver kinds for ``WebhookDeadLetter.receiver_kind``.
RECEIVER_KIND_WEBHOOK = "webhook"
RECEIVER_KIND_AGENT_BOT = "agent_bot"

# enum webhook_type: {account_type: 0, inbox_type: 1}
WEBHOOK_TYPE_ACCOUNT = 0
WEBHOOK_TYPE_INBOX = 1

# Mirrors ``Webhook::ALLOWED_WEBHOOK_EVENTS`` (v4.13.0).
ALLOWED_WEBHOOK_EVENTS: tuple[str, ...] = (
    "conversation_status_changed",
    "conversation_updated",
    "conversation_created",
    "contact_created",
    "contact_updated",
    "message_created",
    "message_updated",
    "webwidget_triggered",
    "inbox_created",
    "inbox_updated",
    "conversation_typing_on",
    "conversation_typing_off",
)


class Webhook(TimestampMixin, table=True):
    __tablename__ = "webhooks"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "url",
            name="index_webhooks_on_account_id_and_url",
        ),
        Index("index_webhooks_account_lookup", "account_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    inbox_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    url: str = Field(sa_column=Column(Text, nullable=False))
    webhook_type: int = Field(
        default=WEBHOOK_TYPE_ACCOUNT,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    subscriptions: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    secret: str | None = Field(default=None, sa_column=Column(String, nullable=True))


class WebhookDeadLetter(SQLModel, table=True):
    """Quarantine row for a webhook delivery that exhausted its
    retries (v2.9). Not a ``TimestampMixin`` subclass because the
    ``updated_at`` semantics don't apply — once a row lands, it's a
    forensic record and shouldn't bump on read.
    """

    __tablename__ = "webhook_dead_letters"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    # ``webhook`` | ``agent_bot`` — string for forward-compat with new
    # receiver kinds (Instagram bot, etc.) that may land later.
    receiver_kind: str = Field(
        sa_column=Column(String(32), nullable=False),
    )
    # Not a real FK — the receiver may be deleted while the dead-letter
    # row sticks around. We still index it so dashboards can group by
    # receiver.
    receiver_id: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    url: str = Field(sa_column=Column(String, nullable=False))
    event_name: str = Field(sa_column=Column(String(64), nullable=False))
    event_id: str | None = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )
    body: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    last_status_code: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    last_error: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    attempts: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=sa_func.now(),
        ),
    )
    last_attempted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


__all__ = [
    "ALLOWED_WEBHOOK_EVENTS",
    "RECEIVER_KIND_AGENT_BOT",
    "RECEIVER_KIND_WEBHOOK",
    "WEBHOOK_TYPE_ACCOUNT",
    "WEBHOOK_TYPE_INBOX",
    "Webhook",
    "WebhookDeadLetter",
]
