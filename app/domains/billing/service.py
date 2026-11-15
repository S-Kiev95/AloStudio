"""Applying Polar's webhooks to the account's subscription (F2 paso 3).

Webhook code must never raise (a payment provider retrying a half-applied
event is worse than a logged error): :func:`handle_webhook` stores the
event first, applies it inside a savepoint, and keeps any error on the
event row to replay it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.billing.models import ACTIVE_STATUSES, AccountSubscription, BillingEvent

log = logging.getLogger(__name__)


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _account_id(data: dict[str, Any]) -> int | None:
    """Our account, from the checkout's metadata or Polar's customer."""
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    for raw in (metadata.get("account_id"), customer.get("external_id")):
        if raw is not None and str(raw).isdigit():
            return int(raw)
    return None


async def subscription_for(session: AsyncSession, account_id: int) -> AccountSubscription | None:
    return (
        await session.exec(
            select(AccountSubscription).where(AccountSubscription.account_id == account_id)
        )
    ).first()


async def _apply_subscription(session: AsyncSession, data: dict[str, Any]) -> None:
    account_id = _account_id(data)
    if account_id is None:
        raise ValueError("subscription without account (metadata.account_id / customer.external_id)")
    sub = await subscription_for(session, account_id)
    if sub is None:
        sub = AccountSubscription(account_id=account_id)
    product = data.get("product") if isinstance(data.get("product"), dict) else {}
    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    sub.provider = "polar"
    sub.external_subscription_id = str(data.get("id") or sub.external_subscription_id or "") or None
    sub.external_customer_id = str(customer.get("id") or data.get("customer_id") or "") or None
    sub.product_id = str(data.get("product_id") or product.get("id") or "") or None
    sub.plan_name = product.get("name") or sub.plan_name
    sub.status = str(data.get("status") or sub.status)
    sub.current_period_end = _parse_dt(data.get("current_period_end"))
    sub.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
    session.add(sub)
    await session.flush()


async def handle_webhook(
    session: AsyncSession, *, webhook_id: str, payload: dict[str, Any]
) -> str:
    """Store and apply one verified Polar event. Returns ``duplicate``,
    ``applied``, ``ignored`` or ``failed``; never raises."""
    event_type = str(payload.get("type") or "")
    existing = (
        await session.exec(select(BillingEvent).where(BillingEvent.webhook_id == webhook_id))
    ).first()
    if existing is not None and existing.processed_at is not None:
        return "duplicate"
    event = existing or BillingEvent(webhook_id=webhook_id, event_type=event_type, payload=payload)
    session.add(event)
    await session.flush()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    outcome = "ignored"
    try:
        async with session.begin_nested():
            if event_type.startswith("subscription."):
                await _apply_subscription(session, data)
                outcome = "applied"
        event.processed_at = datetime.now(UTC)
        event.error = None
    except Exception as exc:
        log.exception("billing.polar.webhook_failed webhook_id=%s type=%s", webhook_id, event_type)
        event.error = f"{type(exc).__name__}: {exc}"[:1000]
        outcome = "failed"
    session.add(event)
    await session.flush()
    return outcome


def present_subscription(sub: AccountSubscription | None) -> dict[str, Any]:
    if sub is None:
        return {"status": "none", "has_access": False}
    return {
        "status": sub.status,
        "has_access": sub.status in ACTIVE_STATUSES,
        "plan_name": sub.plan_name,
        "product_id": sub.product_id,
        "current_period_end": int(sub.current_period_end.timestamp())
        if sub.current_period_end
        else None,
        "cancel_at_period_end": sub.cancel_at_period_end,
    }


__all__ = ["handle_webhook", "present_subscription", "subscription_for"]
