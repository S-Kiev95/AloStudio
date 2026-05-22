"""Instagram connection HTTP endpoints (I.10).

Admin-only. Ships the **manual / advanced** connect path here; the OAuth
flows (Facebook Login + Instagram Login start/callback) layer on in the
follow-up commits using the same ``connect_service``.

Route map:
  * ``POST /api/v1/accounts/{id}/instagram_channels/connect_manual``
  * ``GET  /api/v1/accounts/{id}/instagram_channels/{channel_id}/settings``
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.instagram import connect_service
from app.domains.instagram.schemas import InstagramManualConnect

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/instagram_channels",
    tags=["instagram-connect"],
)


@router.post("/connect_manual", status_code=status.HTTP_200_OK)
async def connect_manual_endpoint(
    payload: InstagramManualConnect,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Create an Instagram inbox+channel from a pasted token and record
    its ``login_type`` (capabilities)."""
    return await connect_service.connect_manual(
        session,
        account=ctx.account,
        name=payload.name,
        instagram_id=payload.instagram_id,
        access_token=payload.access_token,
        login_type=payload.login_type,
        expires_at=payload.expires_at,
    )


@router.get("/{channel_id}/settings")
async def show_channel_settings(
    channel_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Connection capabilities for a channel (login_type + whether
    DELETE media is available)."""
    assert ctx.account.id is not None
    setting = await connect_service.get_channel_setting(
        session, channel_instagram_id=channel_id
    )
    if setting is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return {
        "channel_instagram_id": setting.channel_instagram_id,
        "login_type": setting.login_type,
        "connect_method": setting.connect_method,
        "page_id": setting.page_id,
        "can_delete_media": setting.login_type != "instagram",
    }


__all__ = ["router"]
