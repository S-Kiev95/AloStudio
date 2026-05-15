"""Campaign — scheduled or trigger-based outbound message broadcast.

Ported from:
  reference/chatwoot/app/models/campaign.rb
  reference/chatwoot/db/schema.rb (``campaigns`` table)

Two campaign types:
  * ``ongoing``  — fires on web-widget triggers (rule-based, e.g. URL
    contains "/pricing"). Reads ``trigger_rules`` JSONB.
  * ``one_off``  — fires at ``scheduled_at`` for a given audience
    JSONB ([{type: 'Contact', id: ...}, ...]).

Phase 9.4 ships CRUD only — the scheduler runtime that actually
fires one_off campaigns + processes ongoing widget triggers defers
to Phase 10 hardening (ARQ-backed worker).

``display_id`` is per-account sequential (1, 2, 3, ...). We compute
it in the service rather than via a Postgres BEFORE INSERT trigger
to keep the migration simple — same observable result.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# enum campaign_type: {ongoing: 0, one_off: 1}
CAMPAIGN_TYPE_ONGOING = 0
CAMPAIGN_TYPE_ONE_OFF = 1

# enum campaign_status: {active: 0, completed: 1}
CAMPAIGN_STATUS_ACTIVE = 0
CAMPAIGN_STATUS_COMPLETED = 1


def campaign_type_from_str(s: str | None) -> int:
    if s is None or s == "ongoing":
        return CAMPAIGN_TYPE_ONGOING
    if s == "one_off":
        return CAMPAIGN_TYPE_ONE_OFF
    raise ValueError(f"unknown campaign_type: {s!r}")


def campaign_type_to_str(v: int | None) -> str:
    return "one_off" if v == CAMPAIGN_TYPE_ONE_OFF else "ongoing"


def campaign_status_from_str(s: str | None) -> int:
    if s is None or s == "active":
        return CAMPAIGN_STATUS_ACTIVE
    if s == "completed":
        return CAMPAIGN_STATUS_COMPLETED
    raise ValueError(f"unknown campaign_status: {s!r}")


def campaign_status_to_str(v: int | None) -> str:
    return "completed" if v == CAMPAIGN_STATUS_COMPLETED else "active"


class Campaign(TimestampMixin, table=True):
    __tablename__ = "campaigns"
    __table_args__ = (
        Index("index_campaigns_on_account_id", "account_id"),
        Index("index_campaigns_on_inbox_id", "inbox_id"),
        Index(
            "index_campaigns_on_campaign_status", "campaign_status"
        ),
        Index(
            "index_campaigns_on_campaign_type", "campaign_type"
        ),
        Index("index_campaigns_on_scheduled_at", "scheduled_at"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    display_id: int = Field(sa_column=Column(Integer, nullable=False))
    title: str = Field(sa_column=Column(String, nullable=False))
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    message: str = Field(sa_column=Column(Text, nullable=False))
    sender_id: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    inbox_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    trigger_rules: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    campaign_type: int = Field(
        default=CAMPAIGN_TYPE_ONGOING,
        sa_column=Column(
            Integer, nullable=False, server_default="0"
        ),
    )
    campaign_status: int = Field(
        default=CAMPAIGN_STATUS_ACTIVE,
        sa_column=Column(
            Integer, nullable=False, server_default="0"
        ),
    )
    audience: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    scheduled_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    trigger_only_during_business_hours: bool = Field(
        default=False,
        sa_column=Column(
            Boolean, nullable=False, server_default="false"
        ),
    )
    template_params: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )


__all__ = [
    "CAMPAIGN_STATUS_ACTIVE",
    "CAMPAIGN_STATUS_COMPLETED",
    "CAMPAIGN_TYPE_ONE_OFF",
    "CAMPAIGN_TYPE_ONGOING",
    "Campaign",
    "campaign_status_from_str",
    "campaign_status_to_str",
    "campaign_type_from_str",
    "campaign_type_to_str",
]
