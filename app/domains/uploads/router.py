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
from app.core.errors import ChatwootHTTPException
from app.domains.uploads.email_assets_router import email_asset_url
from app.domains.uploads.images import (
    ImageConversionError,
    to_instagram_jpeg,
)
from app.domains.uploads.public_router import public_media_url
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


def _looks_like_video(file: UploadFile) -> bool:
    """Content-type first, extension as the fallback — browsers leave the
    type empty for some containers (notably .mov on Windows)."""
    if (file.content_type or "").lower().startswith("video/"):
        return True
    name = (file.filename or "").lower()
    return name.endswith((".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"))


@router.post("/instagram_media")
async def upload_instagram_media(
    ctx: Annotated[AccountContext, Depends(account_context)],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """Stage media for an Instagram post.

    Meta's Content Publishing API fetches ``image_url`` / ``video_url`` from
    its own side, so the job here is to hand back a signed **public** URL
    rather than the internal object-store one.

    Images are additionally normalised to JPEG — Meta rejects PNG, which is
    what most screenshots and exports are. Video is stored **as-is**: making
    it publishable would mean transcoding (H.264/AAC in MP4), which needs
    ffmpeg. An MP4 straight off a phone or editor already qualifies; anything
    exotic is rejected by Meta at container creation with its own message.

    Returns ``{url, key, kind}`` — ``url`` goes into the post's
    ``source.image_url`` / ``source.video_url``.
    """
    assert ctx.account.id is not None
    data = await file.read()

    if _looks_like_video(file):
        stored = await store_upload_blob(
            ctx.account.id,
            # Keep the real extension: the public route infers the
            # content-type from the key, and Meta is picky about it.
            filename=file.filename or "video.mp4",
            content_type=file.content_type or "video/mp4",
            data=data,
        )
        return {
            "url": public_media_url(stored["key"]),
            "key": stored["key"],
            "kind": "video",
        }

    try:
        jpeg = to_instagram_jpeg(data)
    except ImageConversionError as exc:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    "No pudimos leer el archivo. Subí una imagen "
                    "(JPG, PNG, WebP…) o un video MP4."
                )
            },
        ) from exc

    stored = await store_upload_blob(
        ctx.account.id,
        filename="instagram.jpg",
        content_type="image/jpeg",
        data=jpeg,
    )
    return {
        "url": public_media_url(stored["key"]),
        "key": stored["key"],
        "kind": "image",
    }


__all__ = ["router"]


@router.post("/email_asset")
async def upload_email_asset(
    ctx: Annotated[AccountContext, Depends(account_context)],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """Store an image for use inside an email template.

    Returns a **permanent** signed URL, unlike every other public link
    here. A message is a copy the recipient keeps and may open a year
    later; a logo behind an expiring link leaves a broken image in every
    letter the organisation ever sent.

    Images only. A mail client will not play a video inline — it would
    arrive as a broken box, so refusing is kinder than storing it.

    Returns ``{url, key}``; ``url`` goes straight into the block's
    ``src``.
    """
    assert ctx.account.id is not None
    if _looks_like_video(file):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    "Los clientes de correo no reproducen video dentro del "
                    "mensaje. Subí una imagen."
                )
            },
        )

    data = await file.read()
    try:
        # Normalised to JPEG for the same reason as the Instagram path:
        # what people upload is usually a PNG screenshot, and every mail
        # client renders JPEG.
        jpeg = to_instagram_jpeg(data)
    except ImageConversionError as exc:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "No pudimos leer el archivo. Subí una imagen (JPG, PNG, WebP…)."
            },
        ) from exc

    stored = await store_upload_blob(
        ctx.account.id,
        filename="email.jpg",
        content_type="image/jpeg",
        data=jpeg,
    )
    return {"url": email_asset_url(stored["key"]), "key": stored["key"]}
