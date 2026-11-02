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
from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, Response, StreamingResponse

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
    # Streamed, not buffered: a reel can be hundreds of MB and Meta may
    # fetch it more than once.
    client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        resp = await client.send(
            client.build_request("GET", signed_read_url(object_url(key))),
            stream=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        await client.aclose()
        raise not_found from exc

    async def _body() -> AsyncIterator[bytes]:
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    content_type = (
        mimetypes.guess_type(key)[0]
        or resp.headers.get("content-type")
        or "application/octet-stream"
    )
    headers = {"Cache-Control": "public, max-age=3600"}
    if resp.headers.get("content-length"):
        headers["Content-Length"] = resp.headers["content-length"]
    return StreamingResponse(_body(), media_type=content_type, headers=headers)


__all__ = ["PUBLIC_MEDIA_TTL_SECONDS", "public_media_url", "router"]


# TikTok checks that we own the URL prefix of these links (``/public/``)
# by fetching a signature file it hands out, served right under it. Its
# name and content are set in Ajustes → Instalación; until then (or for any
# other name) this answers 404 like an unknown path.
verification_router = APIRouter(tags=["uploads"])


@verification_router.get("/public/tiktok{code}.txt", include_in_schema=False)
async def serve_tiktok_verification(code: str) -> PlainTextResponse:
    settings = get_settings()
    name = settings.tiktok_verification_file.strip()
    content = settings.tiktok_verification_content.strip()
    if not name or not content or name != f"tiktok{code}.txt":
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return PlainTextResponse(content)
