"""ReportingEvent — append-only audit row for time-based dashboards.

Ported from:
  reference/chatwoot/app/models/reporting_event.rb
  reference/chatwoot/db/schema.rb (``reporting_events`` table, v4.13.0)

One row per significant state-change on a Conversation, emitted by the
:mod:`app.domains.reporting.listener` dispatcher hook. The reports
endpoints aggregate over these rows for the dashboard cards +
timeseries.

Event names we emit in 7.1 (mirrors the parity-critical subset of
:class:`ReportingEventListener` in v4.13.0):

  * ``conversation_resolved`` — value = seconds from create to resolve.
  * ``first_response``        — value = seconds from last non-human
                                activity to first agent reply.
  * ``reply_time``            — value = seconds from ``waiting_since``
                                to the agent reply.
  * ``conversation_opened``   — value = seconds since last resolve
                                (0 for first-time open).

Deferred (logged but no row emitted in 7.1):
  * ``conversation_bot_handoff`` / ``conversation_bot_resolved`` —
    needs agent-bot infra (Phase 8).
  * ``conversation_captain_inference_*`` — Captain AI (Phase 8).

The ``value_in_business_hours`` column matches Chatwoot's schema but
falls back to ``value`` until working-hours config lands in Phase 9.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# Allowed ``name`` values — Phase 7.1 subset. The set widens in 8 (bot)
# and 9 (Captain) without a schema change since the column is a free
# ``String`` upstream.
REPORTING_EVENT_NAMES: tuple[str, ...] = (
    "conversation_resolved",
    "first_response",
    "reply_time",
    "conversation_opened",
)


class ReportingEvent(TimestampMixin, table=True):
    """A single dashboard-affecting event."""

    __tablename__ = "reporting_events"
    __table_args__ = (
        Index("index_reporting_events_on_account_id", "account_id"),
        Index("index_reporting_events_on_conversation_id", "conversation_id"),
        Index("index_reporting_events_on_inbox_id", "inbox_id"),
        Index("index_reporting_events_on_user_id", "user_id"),
        Index("index_reporting_events_on_name", "name"),
        Index("index_reporting_events_on_created_at", "created_at"),
        # Composite index Chatwoot ships for response-distribution lookups.
        Index(
            "index_reporting_events_for_response_distribution",
            "account_id",
            "name",
            "inbox_id",
            "created_at",
        ),
        # The big ``(account_id, name, created_at)`` index keeps
        # summary reports fast as the table grows.
        Index(
            "reporting_events__account_id__name__created_at",
            "account_id",
            "name",
            "created_at",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    conversation_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=True,
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
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    value: float = Field(sa_column=Column(Float, nullable=False))
    value_in_business_hours: float | None = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )
    event_start_time: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    event_end_time: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


__all__ = [
    "REPORTING_EVENT_NAMES",
    "ReportingEvent",
]
