"""Applying Polar's webhooks to the account's subscription (F2 paso 3).

Webhook code must never raise (a payment provider retrying a half-applied
event is worse than a logged error): :func:`handle_webhook` stores the
event first, applies it inside a savepoint, and keeps any error on the
event row to replay it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.domains.billing.models import (
    ACTIVE_STATUSES,
    AccountSubscription,
    BillingEvent,
    CreditPurchase,
)

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
    # Once trialing, always "had a trial": the next checkout goes without one.
    sub.trial_used = sub.trial_used or sub.status == "trialing" or bool(data.get("trial_start"))
    sub.current_period_end = _parse_dt(data.get("current_period_end"))
    sub.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
    if isinstance(product.get("metadata"), dict):
        sub.plan_features = dict(product["metadata"])
    session.add(sub)
    await session.flush()


# --- AI credits --------------------------------------------------------------
#
# Pay what you want from USD 5; the more it is, the less margin we keep
# (decided by the owner on 2026-11-16). Thresholds on the amount paid
# without taxes, in cents: (from, share of it that becomes credit).
CREDIT_MINIMUM_CENTS = 500
CREDIT_TIERS: tuple[tuple[int, Decimal], ...] = (
    (10_000, Decimal("0.75")),
    (5_000, Decimal("0.65")),
    (CREDIT_MINIMUM_CENTS, Decimal("0.50")),
)


def credit_for(paid_cents: int) -> Decimal:
    """USD of AI credit that ``paid_cents`` buys (0 under the minimum)."""
    for threshold, share in CREDIT_TIERS:
        if paid_cents >= threshold:
            # Half a cent up, like the screen's preview (lib/api/billing.ts).
            return (Decimal(paid_cents) * share / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return Decimal(0)


def _is_credits_order(data: dict[str, Any]) -> bool:
    product = data.get("product") if isinstance(data.get("product"), dict) else {}
    metadata = product.get("metadata") if isinstance(product.get("metadata"), dict) else {}
    return _text(metadata.get("kind")) == "ai_credits"


def _cents(value: Any) -> int:
    return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0


async def _apply_credit_order(session: AsyncSession, event_type: str, data: dict[str, Any]) -> bool:
    """``order.paid`` credits the account once per order; ``order.refunded``
    (or an update carrying a refund) keeps the refunded part. Returns
    whether it was a credits order."""
    if not data.get("id"):
        return False
    order_id = str(data["id"])
    purchase = (
        await session.exec(select(CreditPurchase).where(CreditPurchase.order_id == order_id))
    ).first()
    if purchase is None and not _is_credits_order(data):
        if not isinstance(data.get("product"), dict):
            # Can't tell what was bought: fail, so the event stays to replay
            # instead of a payment lost as "ignored".
            raise ValueError("order without product")
        return False
    if purchase is None:
        if event_type != "order.paid" and not data.get("paid"):
            return True  # not paid yet: ``order.paid`` will come
        account_id = _account_id(data)
        if account_id is None:
            raise ValueError("credits order without account (metadata.account_id / customer.external_id)")
        paid = _cents(data.get("net_amount"))
        purchase = CreditPurchase(
            account_id=account_id,
            order_id=order_id,
            paid_cents=paid,
            credit=credit_for(paid),
            # Polar's order has no paid-at; the payment lands seconds after.
            paid_at=_parse_dt(data.get("created_at")) or datetime.now(UTC),
        )
    purchase.refunded_cents = max(purchase.refunded_cents, _cents(data.get("refunded_amount")))
    session.add(purchase)
    await session.flush()
    return True


def credit_left_of(purchase: CreditPurchase) -> Decimal:
    """The purchase's credit after refunds (a refund takes its share)."""
    if purchase.paid_cents <= 0:
        return Decimal(0)
    kept = max(purchase.paid_cents - purchase.refunded_cents, 0)
    return (purchase.credit * kept / purchase.paid_cents).quantize(Decimal("0.01"))


async def credit_purchases(session: AsyncSession, account_id: int) -> list[CreditPurchase]:
    return list(
        (
            await session.exec(
                select(CreditPurchase)
                .where(CreditPurchase.account_id == account_id)
                .order_by(CreditPurchase.paid_at.desc())  # type: ignore[attr-defined]
            )
        ).all()
    )


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
            elif event_type.startswith("order.") and await _apply_credit_order(
                session, event_type, data
            ):
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


async def trial_used(session: AsyncSession, account_id: int) -> bool:
    """Whether the account already had its free trial (one per account)."""
    sub = await subscription_for(session, account_id)
    return sub is not None and sub.trial_used


async def has_paid_access(session: AsyncSession, account_id: int) -> bool:
    """Always on a single-tenant install (CTC, Enterprise); on a multitenant
    one, only while Polar's subscription is ``active`` or ``trialing``."""
    if not get_settings().multitenant:
        return True
    sub = await subscription_for(session, account_id)
    return sub is not None and sub.status in ACTIVE_STATUSES


# --- What each plan allows (multitenant only) --------------------------------
#
# Read from the Polar product's metadata (``plan_features``), so a plan is
# changed in Polar without a deploy. Channels that are not social networks
# (email, the website chat, the API) come with every plan; ``channels:
# meta`` (Basic) keeps the rest to Meta's networks. A key missing from the
# metadata allows the channel and denies calls.

_META_INBOX_CHANNELS = frozenset({"whatsapp", "facebook", "instagram"})
_OWN_INBOX_CHANNELS = frozenset({"api", "email", "web_widget"})
_META_PUBLISHING_NETWORKS = frozenset({"facebook_page", "instagram", "threads"})


async def _plan_features(session: AsyncSession, account_id: int) -> dict[str, Any] | None:
    """None on a single-tenant install (CTC, Enterprise): everything."""
    if not get_settings().multitenant:
        return None
    sub = await subscription_for(session, account_id)
    return dict(sub.plan_features or {}) if sub else {}


# Metadata typed in Polar's dashboard arrives as text ("true", " Meta ").
def _text(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def _meta_only(features: dict[str, Any] | None) -> bool:
    return features is not None and _text(features.get("channels")) == "meta"


async def plan_allows_inbox_channel(session: AsyncSession, account_id: int, channel_type: str) -> bool:
    if channel_type in _META_INBOX_CHANNELS | _OWN_INBOX_CHANNELS:
        return True
    return not _meta_only(await _plan_features(session, account_id))


async def plan_allows_network(session: AsyncSession, account_id: int, network: str) -> bool:
    if network in _META_PUBLISHING_NETWORKS:
        return True
    return not _meta_only(await _plan_features(session, account_id))


async def plan_allows_calls(session: AsyncSession, account_id: int) -> bool:
    features = await _plan_features(session, account_id)
    return features is None or _text(features.get("whatsapp_calls")) in {"true", "1"}


async def plan_allows(session: AsyncSession, account_id: int) -> dict[str, Any]:
    """What the plan includes, for the panel to dim the rest (the API still
    refuses it): the inbox channels and publishing networks it allows (None:
    all of them) and WhatsApp calls. Everything on a single-tenant install."""
    features = await _plan_features(session, account_id)
    meta_only = _meta_only(features)
    return {
        "inbox_channels": sorted(_META_INBOX_CHANNELS | _OWN_INBOX_CHANNELS) if meta_only else None,
        "networks": sorted(_META_PUBLISHING_NETWORKS) if meta_only else None,
        "whatsapp_calls": features is None or _text(features.get("whatsapp_calls")) in {"true", "1"},
    }


async def plan_usage_cap(session: AsyncSession, account_id: int) -> Decimal | None:
    """The plan's monthly cap on AI spend, in USD, or None (also
    for a value that isn't a positive number)."""
    features = await _plan_features(session, account_id)
    cents = (features or {}).get("usage_cap_usd_cents")
    if isinstance(cents, bool) or not isinstance(cents, int | float | str):
        return None
    try:
        value = Decimal(str(cents).strip())
    except ArithmeticError:
        return None
    if not value.is_finite() or value <= 0:
        return None
    return (value / 100).quantize(Decimal("0.01"))


def plan_upgrade_required() -> ChatwootHTTPException:
    """403 for what the account's plan doesn't include (402 is "no plan")."""
    return ChatwootHTTPException(
        status_code=403,
        detail={
            "error": "Your plan does not include this",
            "code": "plan_upgrade_required",
        },
    )


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


__all__ = [
    "CREDIT_MINIMUM_CENTS",
    "CREDIT_TIERS",
    "credit_for",
    "credit_left_of",
    "credit_purchases",
    "handle_webhook",
    "has_paid_access",
    "plan_allows",
    "plan_allows_calls",
    "plan_allows_inbox_channel",
    "plan_allows_network",
    "plan_upgrade_required",
    "plan_usage_cap",
    "present_subscription",
    "subscription_for",
    "trial_used",
]
