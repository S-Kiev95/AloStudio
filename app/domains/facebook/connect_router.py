"""Connecting Facebook Pages (admin only). Facebook sends the browser back to
the same callback as the Instagram flows; the state's ``flow`` tells them
apart (``instagram.connect_router.oauth_callback``).

  * ``GET  /api/v1/accounts/{id}/facebook_pages/connect/start``
  * ``GET  /api/v1/accounts/{id}/facebook_pages/pending/{nonce}``
  * ``POST /api/v1/accounts/{id}/facebook_pages/pending/{nonce}/{page_id}``
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.domains.facebook import connect_service

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/facebook_pages",
    tags=["facebook-connect"],
)


@router.get("/connect/start")
async def connect_start(
    ctx: Annotated[AccountContext, Depends(require_admin)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    return {"authorize_url": connect_service.start_page_oauth(ctx.account.id)}


@router.get("/pending/{nonce}")
async def pending_pages(
    nonce: Annotated[str, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    return await connect_service.pending_pages(account_id=ctx.account.id, nonce=nonce)


@router.post("/pending/{nonce}/{page_id}", status_code=status.HTTP_200_OK)
async def connect_pending_page(
    nonce: Annotated[str, Path()],
    page_id: Annotated[str, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    return await connect_service.connect_pending_page(
        session, account_id=ctx.account.id, nonce=nonce, page_id=page_id
    )


__all__ = ["router"]
