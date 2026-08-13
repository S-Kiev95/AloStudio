"""Cached ad performance, pulled from Meta's Marketing API.

Attribution (``conversations.ad_id``) answers *which ad brought this
conversation*; these rows answer *what that ad cost*. Together they give
cost per conversation, which is the number a business actually steers on.

Stored **per ad per day** rather than per ad. Reports run over arbitrary
windows ("last 30 days", "vs. previous period"), and spend only lines up
with a conversation count when both are summed over the same days — a
single lifetime total per ad could not answer any windowed question.

Metrics are cached rather than fetched live: Meta rate-limits insights
per ad account, and a reports page that fanned out to the Graph API on
every render would exhaust that quota quickly.
"""

from __future__ import annotations

# ``date`` is aliased: the column is also named ``date``, and a field
# whose name shadows its own annotation cannot be resolved.
from datetime import date as date_type
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin


class AdInsight(TimestampMixin, table=True):
    """One ad's spend + delivery for one day."""

    __tablename__ = "ad_insights"
    __table_args__ = (
        # The sync upserts on this key, so a re-run for an overlapping range
        # corrects figures instead of double-counting them. Meta restates
        # recent days as attribution settles, which makes that essential.
        UniqueConstraint(
            "account_id", "ad_id", "date", name="uniq_ad_insight_per_day"
        ),
        Index("index_ad_insights_on_account_date", "account_id", "date"),
        Index("index_ad_insights_on_ad_id", "ad_id"),
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
        )
    )
    # Matches ``conversations.ad_id`` — the join that turns spend into
    # cost per conversation.
    ad_id: str = Field(sa_column=Column(String, nullable=False))
    ad_name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    date: date_type = Field(sa_column=Column(Date, nullable=False))

    # Money as NUMERIC, never float: summing binary floats across a month of
    # daily rows accumulates error, and this feeds a cost-per-result figure.
    spend: float = Field(
        default=0, sa_column=Column(Numeric(14, 4), nullable=False, server_default="0")
    )
    # Ad accounts are denominated in one currency; kept per row so a report
    # never silently adds pesos to dollars.
    currency: str | None = Field(
        default=None, sa_column=Column(String(8), nullable=True)
    )
    impressions: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, server_default="0")
    )
    clicks: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, server_default="0")
    )
    reach: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, server_default="0")
    )

    # The untouched insights row. Meta adds and renames fields, and keeping
    # the original means a shape we did not anticipate is recoverable
    # without re-querying a window that may have aged out.
    raw: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    synced_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


__all__ = ["AdInsight"]
