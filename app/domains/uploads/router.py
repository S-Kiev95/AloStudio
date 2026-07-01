"""Attachment upload — pre-signed direct-upload URL.

``POST /api/v1/accounts/:account_id/uploads`` returns a short-lived
pre-signed PUT URL the client uploads the file to directly (the bytes
never transit our API), plus the stable ``file_url`` to persist as the
attachment's ``external_url`` when the message is created.

Pragmatic stand-in for Chatwoot's ActiveStorage direct-upload endpoint —
same shape of interaction (presign → client PUT → reference the object),
without the blob bookkeeping.
"""

from __future__ import annotations

import re
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.core.deps import AccountContext, account_context
from app.core.storage import object_url, presigned_put_url

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/uploads",
    tags=["uploads"],
)

_UPLOAD_TTL_SECONDS = 900
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str | None) -> str:
    """Strip any path components + collapse unsafe chars so the key can't
    escape the account prefix."""
    base = (name or "file").strip().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = _UNSAFE.sub("-", base).strip("-.") or "file"
    return cleaned[:120]


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
    key = (
        f"accounts/{ctx.account.id}/uploads/"
        f"{uuid4().hex}/{_safe_filename(payload.filename)}"
    )
    return {
        "key": key,
        "upload_url": presigned_put_url(key, expires=_UPLOAD_TTL_SECONDS),
        "file_url": object_url(key),
        "expires_in": _UPLOAD_TTL_SECONDS,
    }


__all__ = ["router"]
