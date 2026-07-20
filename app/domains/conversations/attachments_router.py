"""Media proxy for stored attachments — authenticated + signed-public.

The object store (MinIO/S3) is internal-only in most deployments — the
browser can't reach a ``localhost:9100`` pre-signed URL. Two doors serve the
bytes from here instead:

* ``/api/v1/accounts/{account_id}/attachments/{id}`` — the dashboard's door.
  The presenter points ``data_url`` here, the browser requests it same-origin
  (cookie → devise headers), and we stream the object back.
* ``/public/attachments/{id}?exp=&sig=`` — Meta's door. Instagram's Send API
  takes a URL and downloads the media *itself*, so the link can't be
  session-gated; it is HMAC-signed against ``secret_key`` and expires
  instead — the same trade a pre-signed S3 URL makes.

Only attachments belonging to the caller's account are served on the
authenticated route (404 otherwise).
"""

from __future__ import annotations

import mimetypes
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.core.signed_links import expiry_from_now, is_valid, sign
from app.core.storage import signed_read_url
from app.domains.conversations.models import Attachment

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/attachments",
    tags=["attachments"],
)

public_router = APIRouter(prefix="/public/attachments", tags=["attachments"])

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# A public link only has to survive Meta's fetch, which happens within
# seconds of the send.
PUBLIC_URL_TTL_SECONDS = 3600


def _not_found() -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=404, detail={"error": "Resource could not be found"}
    )


async def _stream_attachment(att: Attachment) -> Response:
    """Fetch the object server-side (the store is reachable from here even
    when it isn't from the caller) and hand the bytes back."""
    read_url = signed_read_url(att.external_url or "")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(read_url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ChatwootHTTPException(
            status_code=502, detail={"error": "attachment fetch failed"}
        ) from exc

    content_type = (
        (
            mimetypes.guess_type(f"file.{att.extension}")[0]
            if att.extension
            else None
        )
        or resp.headers.get("content-type")
        or "application/octet-stream"
    )
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "private, max-age=3600",
        },
    )


# ---------------------------------------------------------------------------
# Signed public links — Meta fetches outbound media itself
# ---------------------------------------------------------------------------
def _payload(attachment_id: int) -> str:
    """Namespaced so an attachment signature can't be replayed against the
    key-addressed media route (or vice versa)."""
    return f"attachment:{attachment_id}"


def _public_signature(attachment_id: int, expires_at: int) -> str:
    return sign(_payload(attachment_id), expires_at)


def public_attachment_url(
    attachment_id: int, *, ttl_seconds: int = PUBLIC_URL_TTL_SECONDS
) -> str:
    """An unauthenticated, signed, expiring URL for an attachment's bytes.

    Instagram's Send API takes ``payload.url`` and downloads it from Meta's
    side, so the link cannot be session-gated — it is signed + short-lived
    instead. Built off ``app_base_url`` because it has to be reachable from
    the public internet, not just from the tailnet.
    """
    expires_at = expiry_from_now(ttl_seconds)
    sig = _public_signature(attachment_id, expires_at)
    base = get_settings().app_base_url.rstrip("/")
    return (
        f"{base}/public/attachments/{attachment_id}?exp={expires_at}&sig={sig}"
    )


@public_router.get("/{attachment_id}")
async def serve_public_attachment(
    attachment_id: Annotated[int, Path()],
    exp: Annotated[int, Query()],
    sig: Annotated[str, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Stream an attachment to an unauthenticated caller holding a valid
    signature.

    Always 404 (never 401/403) so the endpoint never confirms which ids
    exist to someone probing it.
    """
    if not is_valid(_payload(attachment_id), exp, sig):
        raise _not_found()
    att = await session.get(Attachment, attachment_id)
    if att is None or not att.external_url:
        raise _not_found()
    return await _stream_attachment(att)


@router.get("/{attachment_id}")
async def serve_attachment(
    attachment_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Stream a stored attachment's bytes (account-scoped)."""
    att = await session.get(Attachment, attachment_id)
    if att is None or att.account_id != ctx.account.id or not att.external_url:
        raise _not_found()
    return await _stream_attachment(att)


__all__ = ["public_attachment_url", "public_router", "router"]
