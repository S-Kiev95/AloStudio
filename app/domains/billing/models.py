"""Paid plans per account (F2 paso 3), charged through Polar.

  * :class:`AccountSubscription` — one per account: which plan (the Polar
    product), its state and until when it is paid. Written only from
    Polar's webhooks, so it always matches what Polar charged.
  * :class:`BillingEvent` — every webhook received, by its ``webhook-id``:
    Polar retries deliveries, and a retried one must not apply twice. It
    also keeps what failed, to replay it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# Polar subscription states that give access to the product.
ACTIVE_STATUSES = frozenset({"active", "trialing"})


class AccountSubscription(TimestampMixin, table=True):
    __tablename__ = "account_subscriptions"

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        )
    )
    provider: str = Field(default="polar", sa_column=Column(String(16), nullable=False))
    external_subscription_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True, unique=True)
    )
    external_customer_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    product_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    plan_name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    # incomplete / trialing / active / past_due / canceled / unpaid
    status: str = Field(default="none", sa_column=Column(String(32), nullable=False))
    current_period_end: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    cancel_at_period_end: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # The Polar product's metadata: what the plan allows (``channels``:
    # ``meta`` / ``all``, ``whatsapp_calls``, ``usage_cap_usd_cents``).
    # Edited in Polar, copied here by each subscription webhook.
    plan_features: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    # Which month (AAAA-MM) and level (80/100) of the plan's AI cap the
    # admins were last told, like ``UsageLimit`` does for an admin's cap.
    cap_notified_month: str | None = Field(
        default=None, sa_column=Column(String(7), nullable=True)
    )
    cap_notified_level: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    # The AI credit alerts: which purchase they were about (a new one starts
    # them over) and how far it got (20 = low, 100 = used up).
    credit_notified_purchase_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    credit_notified_level: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    # When the renewal charge first failed (``past_due``): the account keeps
    # access for ``PAST_DUE_GRACE`` from then while Polar retries.
    past_due_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    # The account already had a free trial: no second one (F2).
    trial_used: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # The day an unusually high AI spend was last reported (once a day).
    spike_notified_on: date | None = Field(
        default=None, sa_column=Column(Date, nullable=True)
    )


class BillingEvent(TimestampMixin, table=True):
    __tablename__ = "billing_events"

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    provider: str = Field(default="polar", sa_column=Column(String(16), nullable=False))
    webhook_id: str = Field(sa_column=Column(String, nullable=False, unique=True))
    event_type: str = Field(sa_column=Column(String(64), nullable=False))
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    processed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class CreditPurchase(TimestampMixin, table=True):
    """AI credit bought in Polar (one ``order.paid`` of the credits
    product). The balance is computed from these and the AI spend above the
    plan's cap; nothing is deducted per call. Credit never expires."""

    __tablename__ = "credit_purchases"

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    # Polar's order: a retried webhook must not credit twice.
    order_id: str = Field(sa_column=Column(String, nullable=False, unique=True))
    # What the client paid, without taxes (Polar's ``net_amount``), cents.
    paid_cents: int = Field(sa_column=Column(Integer, nullable=False))
    refunded_cents: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    # USD of AI it buys (the paid amount less the margin of its tier).
    credit: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    paid_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class CreditMonthUsage(TimestampMixin, table=True):
    """AI credit a closed month used (its AI spend above the plan's cap
    then). Frozen once the month is over, so a later change of plan doesn't
    rewrite the past, and the balance doesn't re-read the whole history."""

    __tablename__ = "credit_month_usages"
    __table_args__ = (UniqueConstraint("account_id", "month", name="uniq_credit_month_usages"),)

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    )
    # First day of the month (UTC).
    month: date = Field(sa_column=Column(Date, nullable=False))
    used: Decimal = Field(sa_column=Column(Numeric(12, 6), nullable=False))


__all__ = [
    "ACTIVE_STATUSES",
    "AccountSubscription",
    "BillingEvent",
    "CreditMonthUsage",
    "CreditPurchase",
]
