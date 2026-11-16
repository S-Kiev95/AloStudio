"""Billing endpoints (F2 paso 3):

  * ``GET  /api/v1/accounts/{id}/billing``          — the account's plan.
  * ``GET  /api/v1/accounts/{id}/billing/plans``    — plans to choose from.
  * ``POST /api/v1/accounts/{id}/billing/checkout`` — Polar payment link.
  * ``POST /api/v1/accounts/{id}/billing/portal``   — Polar portal (card,
    invoices, cancel).
  * ``POST /webhooks/polar`` — Polar's events (signature checked).
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import AccountContext, require_billing_admin
from app.domains.billing import polar
from app.domains.billing.service import handle_webhook, present_subscription, subscription_for

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/accounts/{account_id}/billing", tags=["billing"])
webhook_router = APIRouter(tags=["billing"])


class CheckoutBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_id: str


@router.get("")
async def billing_status(
    ctx: Annotated[AccountContext, Depends(require_billing_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    return present_subscription(await subscription_for(session, ctx.account.id))


@router.get("/plans")
async def billing_plans(
    ctx: Annotated[AccountContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    return {"plans": await polar.list_plans()}


@router.post("/checkout")
async def billing_checkout(
    body: CheckoutBody,
    ctx: Annotated[AccountContext, Depends(require_billing_admin)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    base = get_settings().app_base_url.rstrip("/")
    url = await polar.create_checkout(
        account_id=ctx.account.id,
        product_id=body.product_id,
        customer_email=ctx.user.email,
        success_url=f"{base}/accounts/{ctx.account.id}/settings/billing?checkout_id={{CHECKOUT_ID}}",
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
