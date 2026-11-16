"""Paid plans per account (F2 paso 3), charged through Polar.

  * :class:`AccountSubscription` — one per account: which plan (the Polar
    product), its state and until when it is paid. Written only from
    Polar's webhooks, so it always matches what Polar charged.
  * :class:`BillingEvent` — every webhook received, by its ``webhook-id``:
    Polar retries deliveries, and a retried one must not apply twice. It
    also keeps what failed, to replay it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text
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


__all__ = ["ACTIVE_STATUSES", "AccountSubscription", "BillingEvent"]
