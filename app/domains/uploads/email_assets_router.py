"""Permanent signed links for images embedded in email.

Every other public link here expires, and for their purposes that is
right: Meta fetches a post's media once, minutes or days after upload,
and an expiring link limits the blast radius of one leaking.

Email is the opposite medium. The message is a copy the recipient keeps,
read weeks or years later, forwarded, printed. A logo whose URL expired
last month leaves a broken image in every letter the organisation ever
sent — worse than never having uploaded it.

So these links do not expire. The signature is what makes them
unguessable, and that never depended on the expiry; ``sign_permanent``
namespaces them so one can never be replayed as an expiring link, or the
reverse. The bytes are a letterhead the organisation mails to strangers
by design.
"""

from __future__ import annotations

import mimetypes
from typing import Annotated
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.core.signed_links import is_valid_permanent, sign_permanent
from app.core.storage import object_url, signed_read_url

router = APIRouter(prefix="/public/email_asset", tags=["uploads"])

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _payload(key: str) -> str:
    return f"email_asset:{key}"


def email_asset_url(key: str) -> str:
    """The absolute URL a mail client will fetch this image from.

    Absolute because a mail client has no origin to resolve a relative
    path against — the message is read inside Gmail or Outlook, not on
    our domain.
    """
    base = get_settings().app_base_url.rstrip("/")
    sig = sign_permanent(_payload(key))
    return f"{base}/public/email_asset?key={quote(key, safe='')}&sig={sig}"


@router.get("")
async def serve_email_asset(
    key: Annotated[str, Query()],
    sig: Annotated[str, Query()],
) -> Response:
    """Stream the image to an unauthenticated caller with a valid
    signature.

    Always 404, never 401/403, so probing never confirms which keys
    exist. The signature covers the key, so this cannot be walked into an
    arbitrary-object read.
    """
    not_found = ChatwootHTTPException(
        status_code=404, detail={"error": "Resource could not be found"}
    )
    if not is_valid_permanent(_payload(key), sig):
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
        # A day, not an hour: mail clients and their image proxies refetch
        # far more often than a letterhead ever changes.
        headers={"Cache-Control": "public, max-age=86400"},
    )


__all__ = ["email_asset_url", "router"]
