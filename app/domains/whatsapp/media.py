"""Download WhatsApp Cloud media and stash it in our object store.

Ports the Cloud arm of ``Whatsapp::IncomingMessageService#download_attachment_file``:
a two-step Graph fetch (``media_id`` → a short-lived signed URL → the bytes),
then a PUT into MinIO/S3 via the same SigV4 pre-signed-URL machinery the
dashboard uploads use. Returns the stored URL + extension so the inbound
handler can hang an :class:`Attachment` off the message.

Both hops carry ``Authorization: Bearer <api_key>`` — the media URL Meta hands
back (``lookaside.fbsbx.com``) is only reachable with the channel token.
Everything is best-effort: any failure logs and returns ``None`` so a media
message still lands (as an empty/caption-only message) rather than 500-ing the
webhook.
"""

from __future__ import annotations

import logging
import mimetypes
from typing import Any

import httpx

from app.core.storage import object_url, presigned_put_url
from app.domains.inboxes.models import WhatsappChannel
from app.domains.whatsapp.cloud_provider import (
    _PHONE_ID_API_VERSION,
    _api_base,
    _api_headers,
)

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def _download_cloud_media(
    channel: WhatsappChannel, media_id: str
) -> tuple[bytes, str] | None:
    """Return ``(bytes, mime_type)`` for a Cloud media id, or ``None``."""
    cfg = channel.provider_config or {}
    if not isinstance(cfg, dict) or not cfg.get("api_key"):
        return None
    auth = {"Authorization": _api_headers(channel)["Authorization"]}
    meta_url = f"{_api_base()}/{_PHONE_ID_API_VERSION}/{media_id}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            info_resp = await client.get(meta_url, headers=auth)
            info_resp.raise_for_status()
            info = info_resp.json()
            url = info.get("url") if isinstance(info, dict) else None
            mime = (
                info.get("mime_type")
                if isinstance(info, dict)
                else None
            ) or "application/octet-stream"
            if not url:
                return None
            bin_resp = await client.get(url, headers=auth)
            bin_resp.raise_for_status()
            return bin_resp.content, str(mime)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning(
            "whatsapp.media.download_failed media_id=%s err=%s", media_id, exc
        )
        return None


async def _store_bytes(
    *, account_id: int, media_id: str, data: bytes, mime_type: str
) -> dict[str, Any] | None:
    """PUT ``data`` into the object store; return ``{external_url, extension}``."""
    base_mime = mime_type.split(";")[0].strip()
    ext = mimetypes.guess_extension(base_mime) or ""
    key = f"accounts/{account_id}/whatsapp/{media_id}{ext}"
    try:
        put_url = presigned_put_url(key, expires=300)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.put(
                put_url, content=data, headers={"Content-Type": base_mime}
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning(
            "whatsapp.media.store_failed media_id=%s err=%s", media_id, exc
        )
        return None
    return {
        "external_url": object_url(key),
        "extension": ext.lstrip(".") or None,
    }


async def download_and_store_media(
    channel: WhatsappChannel, *, account_id: int, media_id: str
) -> dict[str, Any] | None:
    """Download a Cloud media id and stash it. ``{external_url, extension}``
    or ``None`` on any failure (best-effort)."""
    downloaded = await _download_cloud_media(channel, media_id)
    if downloaded is None:
        return None
    data, mime = downloaded
    return await _store_bytes(
        account_id=account_id, media_id=media_id, data=data, mime_type=mime
    )


__all__ = ["download_and_store_media"]
