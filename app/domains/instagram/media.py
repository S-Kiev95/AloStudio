"""Download Instagram DM media and stash it in our object store.

Ports the download arm of
``Messages::Messenger::MessageBuilder#attach_file`` (``Down.download(url)`` →
ActiveStorage). Instagram hands the file URL straight to us in the webhook
(``message.attachments[].payload.url``) already signed, so unlike WhatsApp
Cloud (:mod:`app.domains.whatsapp.media`) there is no ``media_id`` round-trip
and no ``Authorization`` header — one GET, then a PUT into MinIO/S3 through
the same SigV4 pre-signed machinery the dashboard uploads use.

Best-effort: any failure logs and returns ``None`` so a media DM still lands
(text-only) rather than 500-ing the webhook.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from typing import Any

import httpx

from app.core.storage import object_url, presigned_put_url

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def download_and_store_ig_media(
    *, account_id: int, url: str, key_hint: str
) -> dict[str, Any] | None:
    """Fetch an Instagram attachment URL and stash it.

    ``key_hint`` disambiguates attachments within a message (Meta's ``mid``
    plus the attachment index); it is hashed because a ``mid`` is far too
    long for an object key. Hashing also makes the key deterministic, so a
    duplicate webhook re-delivery overwrites rather than duplicates.

    Returns ``{external_url, extension}``, or ``None`` on any failure.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.content
            mime = resp.headers.get("content-type") or "application/octet-stream"
    except (httpx.HTTPError, ValueError) as exc:
        # Class name only — a signed CDN URL must not leak into logs.
        log.warning(
            "instagram.media.download_failed err=%s", type(exc).__name__
        )
        return None

    base_mime = mime.split(";")[0].strip()
    ext = mimetypes.guess_extension(base_mime) or ""
    slug = hashlib.sha256(key_hint.encode()).hexdigest()[:32]
    key = f"accounts/{account_id}/instagram/{slug}{ext}"
    try:
        put_url = presigned_put_url(key, expires=300)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            put = await client.put(
                put_url, content=data, headers={"Content-Type": base_mime}
            )
            put.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("instagram.media.store_failed err=%s", type(exc).__name__)
        return None
    return {
        "external_url": object_url(key),
        "extension": ext.lstrip(".") or None,
    }


__all__ = ["download_and_store_ig_media"]
