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

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

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


__all__ = [
    "ALLOWED_WEBHOOK_EVENTS",
    "WEBHOOK_TYPE_ACCOUNT",
    "WEBHOOK_TYPE_INBOX",
    "Webhook",
]
