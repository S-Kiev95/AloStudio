"""Facebook Messenger webhook surface.

Two endpoints share the path ``/webhooks/fb_messenger``:

  * ``GET`` — Meta's verification handshake. Echoes ``hub.challenge``
    when ``hub.verify_token`` matches the installation-level
    :class:`Settings.fb_verify_token`. 401 with the canonical error
    envelope otherwise. Mirrors Rails'
    ``ChatwootFbProvider#valid_verify_token?``.

  * ``POST`` — receives Messenger event payloads. Always 200s — Rails'
    ``Webhooks::FacebookEventsJob.perform_later`` queues without a
    channel-lookup short-circuit, so we mirror that. Unknown pages
    drop silently inside the processor.

Anchors:
  reference/chatwoot/config/initializers/facebook_messenger.rb
  reference/chatwoot/app/jobs/webhooks/facebook_events_job.rb
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.core.meta_signature import verify_sha256_signature

router = APIRouter(
    tags=["facebook-webhooks"],
)


# Chatwoot mounts the ``facebook-messenger`` gem at ``/bot`` (see
# ``reference/chatwoot/config/routes.rb`` line 568). We match the
# path so a webhook URL the agent pasted into Meta's app config
# works against either backend interchangeably.
@router.get("/bot")
async def facebook_verify(
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
    hub_verify_token: Annotated[
        str | None, Query(alias="hub.verify_token")
    ] = None,
) -> Any:
    """Meta verification handshake.

    Mirrors Rails' ``ChatwootFbProvider#valid_verify_token?``: compare
    the inbound ``hub.verify_token`` to the installation-level
    ``FB_VERIFY_TOKEN`` env var. Token matches -> echo
    ``hub.challenge``. Empty config (no env var set) refuses every
    request (fail-closed — agents must explicitly opt in).
    """
    expected = get_settings().fb_verify_token
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


@router.post("/bot")
async def facebook_receive(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Receive a Messenger webhook payload.

    Always 200 — Rails ``FacebookEventsJob.perform_later`` queues
    without checking the page first; unknown pages drop silently in
    the processor. Malformed bodies also 200 (Meta retries on 5xx,
    we want the retry loop to break).
    """
    raw = await request.body()

    # Per-POST signature gate (CH-1). Opt-in via
    # ``meta_verify_webhook_signature`` (default OFF for backward-compat,
    # ON in .env.example). The GET hub.verify_token handshake only gates
    # subscription setup — it does NOT authenticate each POST, so with
    # this ON we reject forged Messenger payloads. Fails closed when the
    # secret is unset. Same primitive as the Instagram receiver.
    settings = get_settings()
    if settings.meta_verify_webhook_signature and not verify_sha256_signature(
        raw,
        request.headers.get("X-Hub-Signature-256"),
        settings.meta_app_secret,
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

    from app.domains.facebook.incoming import process_facebook_webhook

    try:
        await process_facebook_webhook(session, payload=payload)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "facebook.webhook.process_failed"
        )

    return {"status": "ok"}


__all__ = ["router"]
