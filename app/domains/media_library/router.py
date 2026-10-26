"""Media library HTTP endpoints.

Route map:
  * ``GET    /api/v1/accounts/{account_id}/media``
  * ``POST   /api/v1/accounts/{account_id}/media`` (multipart ``file``)
  * ``DELETE /api/v1/accounts/{account_id}/media/{asset_id}``

Listing and uploading are open to any account member (like attachment
uploads); deleting is admin-only, like the publications that use it.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Path, UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.media_library import service as svc
from app.domains.media_library.presenters import present_asset

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/media",
    tags=["media"],
)


@router.get("")
async def index_media(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    kind: str | None = None,
    page: int = 1,
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await svc.list_assets(
        session, account_id=ctx.account.id, kind=kind, page=page
    )
    return [present_asset(a) for a in rows]


@router.post("", status_code=status.HTTP_200_OK)
async def upload_media(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    # Starlette spooled the upload to disk; refuse it before pulling it
    # into memory.
    svc.check_upload_size(
        file.size, filename=file.filename, content_type=file.content_type
    )
    asset = await svc.upload_asset(
        session,
        account_id=ctx.account.id,
        filename=file.filename,
        content_type=file.content_type,
        data=await file.read(),
        uploaded_by_id=ctx.user.id,
    )
    return present_asset(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_200_OK)
async def delete_media(
    asset_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    asset = (
        await svc.get_assets(
            session, account_id=ctx.account.id, asset_ids=[asset_id]
        )
    ).get(asset_id)
    if asset is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    key = await svc.delete_asset(session, asset=asset)
    # Remove the stored file only once the row is gone for good, so a failed
    # commit never leaves a row pointing at nothing.
    await session.commit()
    await svc.delete_object(key)
    return {}


__all__ = ["router"]
