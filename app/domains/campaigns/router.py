"""Campaign HTTP endpoints.

Ports ``Api::V1::Accounts::CampaignsController``.

Route map (admin-only):

  * ``GET    /api/v1/accounts/{id}/campaigns``
  * ``POST   /api/v1/accounts/{id}/campaigns``
  * ``GET    /api/v1/accounts/{id}/campaigns/{display_id}``
  * ``PATCH  /api/v1/accounts/{id}/campaigns/{display_id}``
  * ``DELETE /api/v1/accounts/{id}/campaigns/{display_id}``  → head :ok

Note: Chatwoot's controller uses ``display_id`` (per-account sequential)
as the URL path id, NOT the primary key. We mirror that.

Scheduler runtime (one_off campaigns firing at ``scheduled_at`` +
ongoing widget-trigger dispatch) defers to Phase 10 hardening.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.campaigns.presenters import present_campaign
from app.domains.campaigns.schemas import CampaignEnvelope
from app.domains.campaigns.service import (
    campaign_analytics,
    create_campaign,
    destroy_campaign,
    fetch_campaign_by_display_id,
    list_campaigns,
    update_campaign,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/campaigns",
    tags=["campaigns"],
)


async def _find(
    session: AsyncSession, *, account_id: int, display_id: int
):
    campaign = await fetch_campaign_by_display_id(
        session, account_id=account_id, display_id=display_id
    )
    if campaign is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return campaign


@router.get("")
async def index_campaigns(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await list_campaigns(session, account_id=ctx.account.id)
    return [present_campaign(c) for c in rows]


@router.post("", status_code=status.HTTP_200_OK)
async def create_campaign_endpoint(
    payload: CampaignEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    body = payload.campaign.model_dump(exclude_unset=True)
    campaign = await create_campaign(
        session, account_id=ctx.account.id, payload=body
    )
    return present_campaign(campaign)


@router.get("/{display_id}")
async def show_campaign(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    campaign = await _find(
        session, account_id=ctx.account.id, display_id=display_id
    )
    return present_campaign(campaign)


@router.get("/{display_id}/analytics")
async def campaign_analytics_endpoint(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``GET /campaigns/:id/analytics`` — delivery metrics for the campaign:
    conversations created + the sent/delivered/read/failed breakdown of
    its outgoing messages."""
    assert ctx.account.id is not None
    campaign = await _find(
        session, account_id=ctx.account.id, display_id=display_id
    )
    return await campaign_analytics(session, campaign=campaign)


@router.patch("/{display_id}")
async def update_campaign_endpoint(
    display_id: Annotated[int, Path()],
    payload: CampaignEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    campaign = await _find(
        session, account_id=ctx.account.id, display_id=display_id
    )
    body = payload.campaign.model_dump(exclude_unset=True)
    updated = await update_campaign(
        session, campaign=campaign, payload=body
    )
    return present_campaign(updated)


@router.delete("/{display_id}", status_code=status.HTTP_200_OK)
async def destroy_campaign_endpoint(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    campaign = await _find(
        session, account_id=ctx.account.id, display_id=display_id
    )
    await destroy_campaign(session, campaign=campaign)
    return {}


__all__ = ["router"]
