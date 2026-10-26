"""Media library service — upload, list and delete an account's media.

Images are normalised to JPEG on the way in (the same conversion the
Instagram upload uses: Meta rejects PNG, and most screenshots are PNG),
so any image in the library can go to any network. Video is stored as-is;
making it publishable would need transcoding, and an MP4 straight off a
phone already qualifies.
"""

from __future__ import annotations

import logging
import mimetypes

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.errors import ChatwootHTTPException
from app.core.storage import presigned_put_url
from app.domains.media_library.models import (
    MEDIA_KIND_IMAGE,
    MEDIA_KIND_VIDEO,
    MEDIA_KINDS,
    MediaAsset,
)
from app.domains.publishing.models import (
    PUBLICATION_EDITABLE_STATES,
    PUBLICATION_STATE_PUBLISHING,
    Publication,
)
from app.domains.uploads.images import ImageConversionError, to_instagram_jpeg
from app.domains.uploads.public_router import public_media_url
from app.domains.uploads.service import safe_filename, store_upload_blob

log = logging.getLogger(__name__)

# The file is held in memory while it's stored; a phone video for a reel
# fits. Images are decoded too, so they get a much lower cap.
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_IMAGE_BYTES = 30 * 1024 * 1024
# Previews only; publications re-sign their own links when they go out.
PREVIEW_LINK_TTL_SECONDS = 3600
_VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")
_DELETE_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def check_upload_size(size: int | None, *, filename: str | None, content_type: str | None) -> None:
    """Reject an oversized upload before it is read into memory."""
    if size is None:
        return
    limit = (
        MAX_UPLOAD_BYTES if _is_video(filename, content_type) else MAX_IMAGE_BYTES
    )
    if size > limit:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": f"El archivo supera los {limit // (1024 * 1024)} MB."
            },
        )


def _is_video(filename: str | None, content_type: str | None) -> bool:
    """Content-type first, extension as the fallback — browsers leave the
    type empty for some containers (notably .mov on Windows)."""
    if (content_type or "").lower().startswith("video/"):
        return True
    return (filename or "").lower().endswith(_VIDEO_EXTENSIONS)


def _jpeg_name(filename: str | None) -> str:
    stem = safe_filename(filename).rsplit(".", 1)[0] or "imagen"
    return f"{stem}.jpg"


async def upload_asset(
    session: AsyncSession,
    *,
    account_id: int,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    uploaded_by_id: int | None = None,
) -> MediaAsset:
    if not data:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "El archivo está vacío."}
        )
    check_upload_size(len(data), filename=filename, content_type=content_type)

    if _is_video(filename, content_type):
        kind = MEDIA_KIND_VIDEO
        # Keep the real extension: the public route infers the type from it.
        name = safe_filename(filename or "video.mp4")
        stored_type = (
            content_type
            if (content_type or "").startswith("video/")
            else mimetypes.guess_type(name)[0] or "video/mp4"
        )
        payload = data
    else:
        try:
            # Pillow work is CPU-bound: keep it off the event loop.
            payload = await run_in_threadpool(to_instagram_jpeg, data)
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
        kind = MEDIA_KIND_IMAGE
        name = _jpeg_name(filename)
        stored_type = "image/jpeg"

    stored = await store_upload_blob(
        account_id, filename=name, content_type=stored_type, data=payload
    )
    asset = MediaAsset(
        account_id=account_id,
        kind=kind,
        key=stored["key"],
        filename=name,
        content_type=stored_type,
        size_bytes=len(payload),
        uploaded_by_id=uploaded_by_id,
    )
    session.add(asset)
    await session.flush()
    await session.refresh(asset)
    return asset


async def list_assets(
    session: AsyncSession,
    *,
    account_id: int,
    kind: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> list[MediaAsset]:
    """Newest first."""
    per_page = min(max(1, per_page), 200)
    page = max(1, page)
    stmt = select(MediaAsset).where(MediaAsset.account_id == account_id)
    if kind is not None:
        if kind not in MEDIA_KINDS:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": f"kind tiene que ser {' o '.join(MEDIA_KINDS)}"},
            )
        stmt = stmt.where(MediaAsset.kind == kind)
    stmt = stmt.order_by(
        MediaAsset.created_at.desc(),  # type: ignore[attr-defined]
        MediaAsset.id.desc(),  # type: ignore[union-attr]
    )
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    return list((await session.exec(stmt)).all())


async def get_assets(
    session: AsyncSession, *, account_id: int, asset_ids: list[int]
) -> dict[int, MediaAsset]:
    """The account's assets among ``asset_ids``, by id (others are absent)."""
    if not asset_ids:
        return {}
    rows = (
        await session.exec(
            select(MediaAsset).where(
                MediaAsset.account_id == account_id,
                MediaAsset.id.in_(asset_ids),  # type: ignore[union-attr]
            )
        )
    ).all()
    return {row.id: row for row in rows}  # type: ignore[misc]


def asset_public_url(asset: MediaAsset) -> str:
    """A fresh signed link the networks can fetch (full TTL: a scheduled
    post can wait days before Meta downloads it)."""
    return public_media_url(asset.key)


def asset_preview_url(asset: MediaAsset) -> str:
    """A short-lived signed link for showing the asset in the dashboard."""
    return public_media_url(asset.key, ttl_seconds=PREVIEW_LINK_TTL_SECONDS)


async def media_in_use(
    session: AsyncSession, *, account_id: int, media_id: int
) -> bool:
    """Whether a library asset is in a publication that hasn't gone out."""
    found = (
        await session.exec(
            select(Publication.id)
            .where(
                Publication.account_id == account_id,
                Publication.state.in_(  # type: ignore[attr-defined]
                    (*PUBLICATION_EDITABLE_STATES, PUBLICATION_STATE_PUBLISHING)
                ),
                Publication.media.contains([{"media_id": media_id}]),  # type: ignore[attr-defined]
            )
            .limit(1)
        )
    ).first()
    return found is not None


async def delete_object(key: str) -> None:
    """Best-effort: a leftover object costs storage, a failed delete of the
    row would cost the user an asset they can't get rid of. Call it once the
    row's deletion is committed."""
    try:
        async with httpx.AsyncClient(timeout=_DELETE_TIMEOUT) as client:
            resp = await client.delete(presigned_put_url(key, method="DELETE"))
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("media_library.delete_object_failed key=%s err=%s", key, exc)


async def delete_asset(session: AsyncSession, *, asset: MediaAsset) -> str:
    """Delete the row and return the object key to remove after commit.

    The in-use check takes no lock: a publication created in the same
    instant may still reference the asset, and publishing then fails it
    with a clear ``missing_media`` error, which is acceptable."""
    if await media_in_use(
        session, account_id=asset.account_id, media_id=asset.id  # type: ignore[arg-type]
    ):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    "El archivo está en una publicación que todavía no salió. "
                    "Sacalo de la publicación antes de borrarlo."
                )
            },
        )
    key = asset.key
    await session.delete(asset)
    await session.flush()
    return key


__all__ = [
    "MAX_IMAGE_BYTES",
    "MAX_UPLOAD_BYTES",
    "asset_preview_url",
    "asset_public_url",
    "check_upload_size",
    "delete_asset",
    "delete_object",
    "get_assets",
    "list_assets",
    "media_in_use",
    "upload_asset",
]
