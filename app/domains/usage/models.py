"""What each account consumes and what it costs (F6).

  * :class:`UsageRecord` — one row per billable-ish event we see ourselves:
    a WhatsApp message Meta reported pricing for (status webhook), or one
    call to the AI provider with its tokens and estimated cost.
  * :class:`WhatsappCostDay` — what Meta itself says a number cost per day,
    category, pricing type and country (``pricing_analytics`` of the WhatsApp
    Business Account). This is the figure to trust for WhatsApp; the per-
    message rows only split it (by campaign, for instance).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlmodel import Field, SQLModel

from app.core.base_model import TimestampMixin

KIND_WHATSAPP = "whatsapp"
KIND_AI = "ai"


class UsageRecord(TimestampMixin, table=True):
    __tablename__ = "usage_records"
    __table_args__ = (
        Index("index_usage_records_on_account_occurred", "account_id", "occurred_at"),
        UniqueConstraint("account_id", "kind", "source_id", name="uniq_usage_records_source"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    kind: str = Field(sa_column=Column(String(16), nullable=False))
    occurred_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    inbox_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    campaign_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    # WhatsApp: marketing / utility / authentication / service / ...
    # AI: what it was for (agent, instagram_autoreply, help_center, ...).
    category: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    # WhatsApp: regular / free_customer_service / free_entry_point.
    pricing_type: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    billable: bool | None = Field(default=None, sa_column=Column(Boolean, nullable=True))
    model: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    input_tokens: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    cached_tokens: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    output_tokens: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    # Estimated, in ``currency`` (AI: USD list prices). None = unknown.
    cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 6), nullable=True))
    currency: str | None = Field(default=None, sa_column=Column(String(8), nullable=True))
    # WhatsApp: the WAMID (one row per message, however many statuses).
    source_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))


class WhatsappCostDay(SQLModel, table=True):
    __tablename__ = "whatsapp_cost_days"
    __table_args__ = (
        UniqueConstraint(
            "inbox_id",
            "day",
            "pricing_category",
            "pricing_type",
            "country",
            name="uniq_whatsapp_cost_days_bucket",
        ),
        Index("index_whatsapp_cost_days_on_account_day", "account_id", "day"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    inbox_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    day: date = Field(sa_column=Column(Date, nullable=False))
    pricing_category: str = Field(sa_column=Column(String(64), nullable=False))
    pricing_type: str = Field(sa_column=Column(String(64), nullable=False))
    country: str = Field(sa_column=Column(String(8), nullable=False))
    volume: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    cost: Decimal = Field(
        default=Decimal(0), sa_column=Column(Numeric(14, 6), nullable=False, server_default="0")
    )
    currency: str | None = Field(default=None, sa_column=Column(String(8), nullable=True))
    synced_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class UsageLimit(TimestampMixin, table=True):
    """A monthly spend cap an administrator set for one kind of usage.
    Reaching it stops what costs (WhatsApp templates, AI calls) until the
    month ends or the cap goes up; admins are told at 80 % and 100 %."""

    __tablename__ = "usage_limits"
    __table_args__ = (UniqueConstraint("account_id", "kind", name="uniq_usage_limits_kind"),)

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    kind: str = Field(sa_column=Column(String(16), nullable=False))
    monthly_limit: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    # Which month (AAAA-MM) and level (80/100) the admins were last told.
    notified_month: str | None = Field(default=None, sa_column=Column(String(7), nullable=True))
    notified_level: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))


__all__ = ["KIND_AI", "KIND_WHATSAPP", "UsageLimit", "UsageRecord", "WhatsappCostDay"]
