"""WorkingHour — one row per (inbox, day-of-week).

Ported from:
  reference/chatwoot/app/models/working_hour.rb
  reference/chatwoot/app/models/concerns/out_of_offisable.rb
  reference/chatwoot/db/schema.rb (``working_hours`` table)

Seven rows per inbox — one for each day of the week (0=Sunday →
6=Saturday). Each row either marks the day as fully closed, fully
open, or carries explicit open/close hour+minute.

The Phase 9.1 listener wires this into Phase 7.1's ReportingEvent
``value_in_business_hours`` math — until 9.1, that column equals
``value``.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

WEEKDAYS: tuple[str, ...] = (
    "sun",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
)


class WorkingHour(TimestampMixin, table=True):
    """A single day's schedule on an inbox."""

    __tablename__ = "working_hours"
    __table_args__ = (
        Index("index_working_hours_on_account_id", "account_id"),
        Index("index_working_hours_on_inbox_id", "inbox_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    inbox_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    account_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    day_of_week: int = Field(sa_column=Column(Integer, nullable=False))
    closed_all_day: bool = Field(
        default=False,
        sa_column=Column(
            Boolean, nullable=False, server_default="false"
        ),
    )
    open_all_day: bool = Field(
        default=False,
        sa_column=Column(
            Boolean, nullable=False, server_default="false"
        ),
    )
    open_hour: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    open_minutes: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    close_hour: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    close_minutes: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )


# Updatable fields per the Rails ``OFFISABLE_ATTRS`` constant.
OFFISABLE_ATTRS: tuple[str, ...] = (
    "day_of_week",
    "closed_all_day",
    "open_hour",
    "open_minutes",
    "close_hour",
    "close_minutes",
    "open_all_day",
)


__all__ = ["OFFISABLE_ATTRS", "WEEKDAYS", "WorkingHour"]
