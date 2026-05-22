"""Instagram DM webhook surface.

Two endpoints share the path ``/webhooks/instagram``:

  * ``GET`` — Meta's verification handshake. Echoes ``hub.challenge``
    when ``hub.verify_token`` matches the installation-level
    :class:`Settings.ig_verify_token`. 401 with the canonical error
    envelope otherwise. Mirrors Rails'
    ``Webhooks::InstagramController#valid_token?``.

  * ``POST`` — receives Instagram event payloads. Body must have
    ``object == 'instagram'`` (Rails: ``params['object'].casecmp(
    'instagram').zero?``); anything else gets a 422. Otherwise we
    200-ack and dispatch to the inbound processor.

Anchors:
  reference/chatwoot/app/controllers/webhooks/instagram_controller.rb
  reference/chatwoot/config/routes.rb
    (``get/post 'webhooks/instagram'``)
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException

router = APIRouter(
    tags=["instagram-webhooks"],
)


def _verify_signature(
    raw_body: bytes, header: str | None, secret: str
) -> bool:
    """Validate Meta's ``X-Hub-Signature-256: sha256=<hmac>`` header.

    HMAC-SHA256 of the raw request body keyed by the app secret. Uses a
    constant-time compare. Returns False on a missing/malformed header."""
    if not header or not header.startswith("sha256="):
        return False
    provided = header.split("=", 1)[1]
    expected = hmac.new(
        secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, provided)


@router.get("/webhooks/instagram")
async def instagram_verify(
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
    hub_verify_token: Annotated[
        str | None, Query(alias="hub.verify_token")
    ] = None,
) -> Any:
    """Meta verification handshake.

    Empty / unset ``ig_verify_token`` setting refuses every request
    (fail-closed default — agents must explicitly opt in by setting
    the env var).
    """
    expected = get_settings().ig_verify_token
    if (
        not expected
        or hub_verify_token is None
        or hub_verify_token != expected
    ):
        raise ChatwootHTTPException(
            status_code=401,
            detail={"error": "Error; wrong verify token"},
        )
    return hub_challenge or ""


@router.post("/webhooks/instagram")
async def instagram_receive(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Receive an Instagram webhook payload.

    Mirrors Rails' object-gate: ``params['object'].casecmp(
    'instagram').zero?``. Anything else returns 422.

    Once the gate passes, the call always 200s — Rails queues the
    events job without a channel-existence check.

    Signature check (I.8 own-extension): gated behind the explicit
    ``settings.meta_verify_webhook_signature`` flag (default OFF) so the
    Phase 5e DM mirror keeps its original unsigned behaviour. When the
    flag is ON, the ``X-Hub-Signature-256`` HMAC must validate against
    ``meta_app_secret`` or we 401 (fail closed if the secret is unset).
    """
    raw = await request.body()

    settings = get_settings()
    if settings.meta_verify_webhook_signature:
        secret = settings.meta_app_secret
        if not secret or not _verify_signature(
            raw, request.headers.get("X-Hub-Signature-256"), secret
        ):
            raise ChatwootHTTPException(
                status_code=401,
                detail={"error": "Invalid signature"},
            )

    import json

    try:
        payload = json.loads(raw)
    except Exception:  # noqa: BLE001
        return {"status": "ok"}

    if not isinstance(payload, dict):
        return {"status": "ok"}

    obj = str(payload.get("object") or "")
    if obj.lower() != "instagram":
        raise ChatwootHTTPException(
            status_code=422,
            detail={"error": "Not an instagram webhook event"},
        )

    from app.domains.instagram.incoming import process_instagram_webhook
    from app.domains.instagram.webhook_changes import (
        process_instagram_changes,
    )

    import logging

    # DM path (Phase 5e) — entry[].messaging[].
    try:
        await process_instagram_webhook(session, payload=payload)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception(
            "instagram.webhook.process_failed"
        )

    # Comments / mentions / story_insights (I.8) — entry[].changes[].
    try:
        await process_instagram_changes(session, payload=payload)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception(
            "instagram.webhook.changes_failed"
        )

    return {"status": "ok"}


__all__ = ["router"]
