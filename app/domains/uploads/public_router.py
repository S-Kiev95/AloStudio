"""Signed public links for uploaded post media.

Instagram's Content Publishing API takes ``image_url`` / ``video_url`` and
downloads the file from Meta's own side, so media staged for a post has to be
reachable without a session — our object store is internal-only and the
dashboard's proxy is cookie-gated.

Unlike the DM-attachment link (minutes), these are long-lived on purpose: a
post can be *scheduled*, and Meta only fetches at publish time, which may be
days after the upload. The trade is deliberate — the bytes are an image the
user is about to publish publicly on Instagram anyway, and the link is still
signed (unguessable) and expiring.
"""

from __future__ import annotations

import mimetypes
from typing import Annotated

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.core.signed_links import expiry_from_now, is_valid, sign
from app.core.storage import object_url, signed_read_url

router = APIRouter(prefix="/public/media", tags=["uploads"])

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Long enough to cover a scheduled post (see module docstring).
PUBLIC_MEDIA_TTL_SECONDS = 30 * 24 * 3600


def _payload(key: str) -> str:
    """Namespaced so this signature can't be replayed against the
    attachment route (or vice versa)."""
    return f"media:{key}"


def public_media_url(
    key: str, *, ttl_seconds: int = PUBLIC_MEDIA_TTL_SECONDS
) -> str:
    """A signed, expiring URL Meta can fetch the object at."""
    expires_at = expiry_from_now(ttl_seconds)
    sig = sign(_payload(key), expires_at)
    base = get_settings().app_base_url.rstrip("/")
    from urllib.parse import quote

    return (
        f"{base}/public/media"
        f"?key={quote(key, safe='')}&exp={expires_at}&sig={sig}"
    )


@router.get("")
async def serve_public_media(
    key: Annotated[str, Query()],
    exp: Annotated[int, Query()],
    sig: Annotated[str, Query()],
) -> Response:
    """Stream an object-store blob to an unauthenticated caller holding a
    valid signature.

    Always 404 (never 401/403) so the endpoint never confirms which keys
    exist to someone probing it. The signature covers the key, so this can't
    be walked into an arbitrary-object read.
    """
    not_found = ChatwootHTTPException(
        status_code=404, detail={"error": "Resource could not be found"}
    )
    if not is_valid(_payload(key), exp, sig):
        raise not_found
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(signed_read_url(object_url(key)))
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise not_found from exc

    content_type = (
        mimetypes.guess_type(key)[0]
        or resp.headers.get("content-type")
        or "application/octet-stream"
    )
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


__all__ = ["PUBLIC_MEDIA_TTL_SECONDS", "public_media_url", "router"]
