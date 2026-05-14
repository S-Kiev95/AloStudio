"""Webhook HTTP endpoints.

Ports ``Api::V1::Accounts::WebhooksController``.

Route map (admin-only on all paths — Chatwoot's ``WebhookPolicy``):

  * ``GET    /api/v1/accounts/{id}/webhooks``
  * ``POST   /api/v1/accounts/{id}/webhooks``
  * ``PATCH  /api/v1/accounts/{id}/webhooks/{id}``
  * ``DELETE /api/v1/accounts/{id}/webhooks/{id}``           → head :ok

Wire shape (matches Chatwoot's nested ``payload.webhook(s)``):

  * ``index``  → ``{"payload": {"webhooks": [<webhook>, ...]}}``
  * ``create`` → ``{"payload": {"webhook": <webhook>}}``
  * ``update`` → ``{"payload": {"webhook": <webhook>}}``
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import Inbox
from app.domains.webhooks.presenters import (
    envelope_index,
    envelope_one,
    present_webhook,
)
from app.domains.webhooks.schemas import WebhookEnvelope
from app.domains.webhooks.service import (
    create_webhook,
    destroy_webhook,
    fetch_webhook,
    list_webhooks,
    update_webhook,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/webhooks",
    tags=["webhooks"],
)


async def _present(
    session: AsyncSession, webhook
) -> dict[str, Any]:
    inbox: Inbox | None = None
    if webhook.inbox_id is not None:
        inbox = await session.get(Inbox, webhook.inbox_id)
    return present_webhook(webhook, inbox=inbox)


async def _find(
    session: AsyncSession, *, account_id: int, webhook_id: int
):
    webhook = await fetch_webhook(
        session, account_id=account_id, webhook_id=webhook_id
    )
    if webhook is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return webhook


@router.get("")
async def index_webhooks(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    rows = await list_webhooks(session, account_id=ctx.account.id)
    bodies = [await _present(session, w) for w in rows]
    return envelope_index(bodies)


@router.post("", status_code=status.HTTP_200_OK)
async def create_webhook_endpoint(
    payload: WebhookEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    body = payload.webhook.model_dump(exclude_unset=True)
    webhook = await create_webhook(
        session, account_id=ctx.account.id, payload=body
    )
    return envelope_one(await _present(session, webhook))


@router.patch("/{webhook_id}")
async def update_webhook_endpoint(
    webhook_id: Annotated[int, Path()],
    payload: WebhookEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    webhook = await _find(
        session, account_id=ctx.account.id, webhook_id=webhook_id
    )
    body = payload.webhook.model_dump(exclude_unset=True)
    updated = await update_webhook(
        session, webhook=webhook, payload=body
    )
    return envelope_one(await _present(session, updated))


@router.delete("/{webhook_id}", status_code=status.HTTP_200_OK)
async def destroy_webhook_endpoint(
    webhook_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    webhook = await _find(
        session, account_id=ctx.account.id, webhook_id=webhook_id
    )
    await destroy_webhook(session, webhook=webhook)
    return {}


__all__ = ["router"]
