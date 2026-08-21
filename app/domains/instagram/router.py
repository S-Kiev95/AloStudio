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

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.core.meta_signature import verify_against_any_secret

router = APIRouter(
    tags=["instagram-webhooks"],
)


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
    # Meta requires the raw challenge (no JSON quoting) — see whatsapp/router.
    return PlainTextResponse(hub_challenge or "")


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
    flag is ON, the ``X-Hub-Signature-256`` HMAC must validate or we 401
    (fail closed when no secret is configured).

    **Two secrets, not one.** This endpoint receives events from both
    Meta apps: an account connected through Instagram Login is
    subscribed by the *Instagram* app and signed with its secret, one
    connected through Facebook Login by the Facebook app. Checking only
    ``meta_app_secret`` 401s every event from the other half — and a
    stream of 401s is how Meta decides an endpoint is broken and stops
    delivering.
    """
    raw = await request.body()

    settings = get_settings()
    if settings.meta_verify_webhook_signature and not verify_against_any_secret(
        raw,
        request.headers.get("X-Hub-Signature-256"),
        (settings.meta_instagram_app_secret, settings.meta_app_secret),
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

    import logging

    from app.domains.instagram.incoming import process_instagram_webhook
    from app.domains.instagram.webhook_changes import (
        process_instagram_changes,
    )

    # DM path (Phase 5e) — entry[].messaging[].
    try:
        await process_instagram_webhook(session, payload=payload)
    except Exception:
        logging.getLogger(__name__).exception(
            "instagram.webhook.process_failed"
        )

    # Comments / mentions / story_insights (I.8) — entry[].changes[].
    try:
        await process_instagram_changes(session, payload=payload)
    except Exception:
        logging.getLogger(__name__).exception(
            "instagram.webhook.changes_failed"
        )

    return {"status": "ok"}


__all__ = ["router"]
