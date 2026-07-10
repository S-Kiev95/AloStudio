"""Attachment upload — pre-signed direct-upload URL (dashboard surface).

``POST /api/v1/accounts/:account_id/uploads`` returns a short-lived
pre-signed PUT URL the client uploads the file to directly (the bytes
never transit our API), plus the stable ``file_url`` to persist as the
attachment's ``external_url`` when the message is created.

The signing itself lives in :mod:`app.domains.uploads.service` so the
public widget surface can reuse it verbatim.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, ConfigDict

from app.core.deps import AccountContext, account_context
from app.domains.uploads.service import presign_upload, store_upload_blob

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/uploads",
    tags=["uploads"],
)


class UploadRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str | None = None
    content_type: str | None = None


@router.post("")
async def create_upload(
    payload: UploadRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
) -> dict[str, Any]:
    """Mint a pre-signed PUT URL for an attachment, namespaced under the
    account. Any account member may request one."""
    assert ctx.account.id is not None
    return presign_upload(ctx.account.id, payload.filename)


@router.post("/blob")
async def upload_blob(
    ctx: Annotated[AccountContext, Depends(account_context)],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """Server-side upload — the browser POSTs the file through our API and
    we store it. Use this when the object store isn't reachable from the
    browser (internal MinIO); returns ``{key, file_url}``."""
    assert ctx.account.id is not None
    data = await file.read()
    return await store_upload_blob(
        ctx.account.id,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
    )


__all__ = ["router"]
