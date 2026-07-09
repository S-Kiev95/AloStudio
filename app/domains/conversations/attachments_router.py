"""Authenticated media proxy for stored attachments.

The object store (MinIO/S3) is internal-only in most deployments — the
browser can't reach a ``localhost:9100`` pre-signed URL. This endpoint lets
the dashboard fetch an attachment's bytes through the same authenticated BFF
path it uses for the API: the presenter points ``data_url`` here, the browser
requests it same-origin (cookie → devise headers), and we stream the object
back after fetching it server-side.

Only attachments belonging to the caller's account are served (404 otherwise).
"""

from __future__ import annotations

import mimetypes
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Path
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.core.storage import signed_read_url
from app.domains.conversations.models import Attachment

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/attachments",
    tags=["attachments"],
)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


@router.get("/{attachment_id}")
async def serve_attachment(
    attachment_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Stream a stored attachment's bytes (account-scoped)."""
    att = await session.get(Attachment, attachment_id)
    if (
        att is None
        or att.account_id != ctx.account.id
        or not att.external_url
    ):
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )

    # Fetch the object server-side (the store is reachable from here even when
    # it isn't from the browser). ``signed_read_url`` presigns our-bucket
    # objects and passes external URLs through unchanged.
    read_url = signed_read_url(att.external_url)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(read_url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ChatwootHTTPException(
            status_code=502, detail={"error": "attachment fetch failed"}
        ) from exc

    content_type = (
        mimetypes.guess_type(f"file.{att.extension}")[0]
        if att.extension
        else None
    ) or resp.headers.get("content-type") or "application/octet-stream"
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "private, max-age=3600",
        },
    )


__all__ = ["router"]
