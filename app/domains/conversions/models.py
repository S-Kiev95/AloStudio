"""Conversions API (F17).

A conversation that started from a click-to-WhatsApp ad carries the click's
id (``Conversation.ad_click_id``, Meta's ``ctwa_clid``). When something in it
turns into a lead or a sale (a CRM opportunity is opened, qualified or won; a
conversation closes with a reason the account maps), an event is queued here
and the 5-minute tick sends it to the dataset Meta links to the number. Meta
then learns which ads bring customers, not just chats.

Meta does not deduplicate: each event goes once per conversation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

EVENTS = ("LeadSubmitted", "QualifiedLead", "Purchase")
STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
# A pending event is retried by the tick until this many attempts failed.
MAX_ATTEMPTS = 5


class ConversionSettings(TimestampMixin, table=True):
    """Whether an account tells Meta about its conversions, and when."""

    __tablename__ = "conversion_settings"

    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
        )
    )
    enabled: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # For values that do not bring their own (a closing reason's value).
    currency: str = Field(
        default="USD", sa_column=Column(String(3), nullable=False, server_default="USD")
    )
    # ``{opportunity_created, opportunity_qualified, opportunity_won: event | None,
    # closing: {reason: {event, value}}}``; None means the defaults.
    rules: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True), nullable=True)
    )


class ConversionDataset(TimestampMixin, table=True):
    """The dataset Meta links to a WhatsApp number, where its events go."""

    __tablename__ = "conversion_datasets"

    inbox_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("inboxes.id", ondelete="CASCADE"), primary_key=True
        )
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    dataset_id: str = Field(sa_column=Column(String(64), nullable=False))


class ConversionEvent(TimestampMixin, table=True):
    """One event for Meta, queued, sent or given up on."""

    __tablename__ = "conversion_events"
    __table_args__ = (
        UniqueConstraint("conversation_id", "event_name", name="uniq_conversion_event_per_conversation"),
        Index("index_conversion_events_on_account_created", "account_id", "created_at"),
        Index("index_conversion_events_on_status", "status"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    conversation_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
        )
    )
    inbox_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    event_name: str = Field(sa_column=Column(String(32), nullable=False))
    # What set it off (``opportunity_won``, ``closing``…) and on what (the
    # opportunity's title, the closing reason), for the log.
    trigger: str = Field(sa_column=Column(String(32), nullable=False))
    detail: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    value: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 2), nullable=True))
    currency: str | None = Field(default=None, sa_column=Column(String(3), nullable=True))
    status: str = Field(
        default=STATUS_PENDING,
        sa_column=Column(String(16), nullable=False, server_default=STATUS_PENDING),
    )
    attempts: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    sent_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


__all__ = [
    "EVENTS",
    "MAX_ATTEMPTS",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_SENT",
    "ConversionDataset",
    "ConversionEvent",
    "ConversionSettings",
]
