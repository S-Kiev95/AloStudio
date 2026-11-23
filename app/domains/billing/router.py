"""Billing endpoints (F2 paso 3):

  * ``GET  /api/v1/accounts/{id}/billing``          — the account's plan.
  * ``GET  /api/v1/accounts/{id}/billing/plans``    — plans to choose from.
  * ``POST /api/v1/accounts/{id}/billing/checkout`` — Polar payment link.
  * ``POST /api/v1/accounts/{id}/billing/portal``   — Polar portal (card,
    invoices, cancel).
  * ``GET  /api/v1/accounts/{id}/billing/credits``  — AI credit: balance,
    tiers and purchases.
  * ``POST /api/v1/accounts/{id}/billing/credits/checkout`` — Polar payment
    link to buy credit for an amount.
  * ``POST /webhooks/polar`` — Polar's events (signature checked).
"""

from __future__ import annotations

import json
import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import AccountContext, account_membership, require_billing_admin
from app.domains.billing import polar
from app.domains.billing.service import (
    CREDIT_MINIMUM_CENTS,
    CREDIT_TIERS,
    credit_left_of,
    credit_purchases,
    handle_webhook,
    plan_allows,
    plan_usage_cap,
    present_subscription,
    subscription_for,
    trial_used,
)
from app.domains.usage.limits import ai_month_spend, credit_balance

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/accounts/{account_id}/billing", tags=["billing"])
webhook_router = APIRouter(tags=["billing"])


class CheckoutBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_id: str


class CreditsCheckoutBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # USD, without taxes (Polar adds them per country).
    amount: float = Field(ge=CREDIT_MINIMUM_CENTS / 100, le=10_000)


@router.get("")
async def billing_status(
    # Any member: the app shows agents "elegí un plan" / "pedile al admin"
    # from it. Paying and the portal stay admin-only.
    ctx: Annotated[AccountContext, Depends(account_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    out = present_subscription(await subscription_for(session, ctx.account.id))
    out["allows"] = await plan_allows(session, ctx.account.id)
    cap = await plan_usage_cap(session, ctx.account.id)
    if cap is not None:
        # The plan and its state matter more than the meter: a failing sum
        # leaves the meter out instead of the whole answer.
        try:
            spent = await ai_month_spend(session, ctx.account.id)
            balance = await credit_balance(session, ctx.account.id)
        except Exception:
            log.exception("billing.usage_failed account_id=%s", ctx.account.id)
        else:
            out["usage"] = {
                "cap": float(cap),
                "spent": round(float(spent), 2),
                "currency": "USD",
                "credit_balance": float(balance),
            }
    return out


@router.get("/credits")
async def billing_credits(
    ctx: Annotated[AccountContext, Depends(require_billing_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    purchases = await credit_purchases(session, ctx.account.id)
    return {
        "balance": float(await credit_balance(session, ctx.account.id)),
        "currency": "USD",
        "minimum": CREDIT_MINIMUM_CENTS / 100,
        # Cheapest tier last, as the backend checks them.
        "tiers": [{"from": cents / 100, "share": float(share)} for cents, share in CREDIT_TIERS],
        "purchases": [
            {
                "id": p.id,
                "paid": p.paid_cents / 100,
                "credit": float(credit_left_of(p)),
                "refunded": p.refunded_cents > 0,
                "paid_at": int(p.paid_at.timestamp()),
            }
            for p in purchases
        ],
    }


@router.post("/credits/checkout")
async def billing_credits_checkout(
    body: CreditsCheckoutBody,
    ctx: Annotated[AccountContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    base = get_settings().app_base_url.rstrip("/")
    url = await polar.create_checkout(
        account_id=ctx.account.id,
        product_id=await polar.credits_product_id(),
        customer_email=ctx.user.email,
        success_url=f"{base}/accounts/{ctx.account.id}/settings/billing?credits_checkout={{CHECKOUT_ID}}",
        amount_cents=int((Decimal(str(body.amount)) * 100).quantize(Decimal(1), ROUND_HALF_UP)),
    )
    return {"url": url}


@router.get("/plans")
async def billing_plans(
    ctx: Annotated[AccountContext, Depends(require_billing_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    plans = await polar.list_plans()
    if await trial_used(session, ctx.account.id):
        # One free trial per account: the checkout goes without it too.
        plans = [{**p, "trial_days": None} for p in plans]
    return {"plans": plans}


@router.post("/checkout")
async def billing_checkout(
    body: CheckoutBody,
    ctx: Annotated[AccountContext, Depends(require_billing_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    base = get_settings().app_base_url.rstrip("/")
    url = await polar.create_checkout(
        account_id=ctx.account.id,
        product_id=body.product_id,
        customer_email=ctx.user.email,
        success_url=f"{base}/accounts/{ctx.account.id}/settings/billing?checkout_id={{CHECKOUT_ID}}",
        allow_trial=not await trial_used(session, ctx.account.id),
    )
    return {"url": url}


@router.post("/portal")
async def billing_portal(
    ctx: Annotated[AccountContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    return {"url": await polar.customer_portal_url(account_id=ctx.account.id)}


@webhook_router.post("/webhooks/polar")
async def polar_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    body = await request.body()
    webhook_id = request.headers.get("webhook-id", "")
    ok = polar.verify_signature(
        body=body,
        webhook_id=webhook_id,
        timestamp=request.headers.get("webhook-timestamp", ""),
        signature=request.headers.get("webhook-signature", ""),
        secret=get_settings().polar_webhook_secret,
    )
    if not ok:
        log.warning("billing.polar.bad_signature webhook_id=%s", webhook_id)
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    try:
        payload = json.loads(body)
    except ValueError:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    if not isinstance(payload, dict):
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    outcome = await handle_webhook(session, webhook_id=webhook_id, payload=payload)
    await session.commit()
    log.info("billing.polar.webhook webhook_id=%s type=%s outcome=%s", webhook_id, payload.get("type"), outcome)
    # 2xx even when applying failed: the event is stored with its error and
    # a retry from Polar wouldn't fix our side.
    return Response(status_code=status.HTTP_202_ACCEPTED)


__all__ = ["router", "webhook_router"]
