"""``/api/v1/notification_subscriptions`` — the current user's web-push
endpoints (RFC 8291). User-scoped like ``/api/v1/profile``.

Ports ``Api::V1::NotificationSubscriptionsController`` (create + destroy),
plus a ``GET /vapid_key`` so the browser can call ``PushManager.subscribe``
with the server's VAPID public key.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import current_user
from app.core.errors import ChatwootHTTPException
from app.domains.notifications.models import (
    NOTIFICATION_SUBSCRIPTION_BROWSER_PUSH,
    NotificationSubscription,
)
from app.domains.users.models import User

router = APIRouter(
    prefix="/api/v1/notification_subscriptions",
    tags=["notification_subscriptions"],
)


class _SubscriptionBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subscription_type: str | None = None
    subscription_attributes: dict[str, Any] = {}


class _SubscriptionEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    notification_subscription: _SubscriptionBody


class _UnsubscribeBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    endpoint: str | None = None


def _present(sub: NotificationSubscription) -> dict[str, Any]:
    return {
        "id": sub.id,
        "subscription_type": "browser_push",
        "subscription_attributes": sub.subscription_attributes or {},
    }


@router.get("/vapid_key")
async def vapid_key() -> dict[str, Any]:
    """The public VAPID key the browser needs to subscribe. ``enabled`` is
    False when web-push isn't configured — the frontend hides the toggle."""
    s = get_settings()
    return {
        "public_key": s.vapid_public_key,
        "enabled": bool(s.vapid_public_key and s.vapid_private_key),
    }


@router.post("", status_code=status.HTTP_200_OK)
async def create_subscription(
    payload: _SubscriptionEnvelope,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Register (or refresh) the caller's browser push subscription."""
    attrs = payload.notification_subscription.subscription_attributes or {}
    endpoint = attrs.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "subscription_attributes.endpoint is required"},
        )
    # Upsert by identifier (the push endpoint): re-subscribing the same
    # browser — or a different user on a shared device — reuses the row.
    existing = (
        await session.exec(
            select(NotificationSubscription).where(
                NotificationSubscription.identifier == endpoint
            )
        )
    ).first()
    if existing is not None:
        existing.user_id = user.id
        existing.subscription_attributes = attrs
        sub = existing
    else:
        sub = NotificationSubscription(
            user_id=user.id,
            identifier=endpoint,
            subscription_type=NOTIFICATION_SUBSCRIPTION_BROWSER_PUSH,
            subscription_attributes=attrs,
        )
    session.add(sub)
    await session.flush()
    await session.refresh(sub)
    return _present(sub)


@router.delete("", status_code=status.HTTP_200_OK)
async def destroy_subscription(
    payload: _UnsubscribeBody,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE {endpoint}`` — drop the caller's subscription for that
    endpoint (Rails matches on the subscription token). ``head :ok``."""
    if payload.endpoint:
        sub = (
            await session.exec(
                select(NotificationSubscription).where(
                    NotificationSubscription.identifier == payload.endpoint,
                    NotificationSubscription.user_id == user.id,
                )
            )
        ).first()
        if sub is not None:
            await session.delete(sub)
            await session.flush()
    return {}


__all__ = ["router"]
