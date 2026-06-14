"""Bandwidth SMS webhook surface — ``POST /webhooks/sms/<phone>``.

Anchors:
  reference/chatwoot/app/controllers/webhooks/sms_controller.rb
  reference/chatwoot/config/routes.rb
    (post 'webhooks/sms/:phone_number')

The phone number lives in the URL path because Bandwidth's webhook
config is per-application (one app per number); we resolve the
channel by the URL phone, not by anything in the body. Always 200s
to break Bandwidth's retry loop on malformed payloads.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.basic_auth import verify_basic_auth
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException

router = APIRouter(
    tags=["bandwidth-webhooks"],
)


@router.post("/webhooks/sms/{phone_number}")
async def bandwidth_receive(
    phone_number: Annotated[str, Path()],
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Receive a Bandwidth SMS webhook.

    Always 200s — Bandwidth retries on 5xx, so unknown phones,
    delivery callbacks (skipped in 5f.4), and malformed bodies must
    all ack.

    Optional per-channel HTTP Basic Auth (CH-1): Bandwidth secures
    callbacks with Basic Auth (not an HMAC signature like the Meta
    channels). When the resolved channel's ``provider_config`` carries
    ``webhook_user`` + ``webhook_pass``, the inbound ``Authorization``
    header must match or the POST 401s — closing the "anyone who knows
    the callback URL can inject SMS" gap. Absent those keys the receiver
    behaves as before (parity with Chatwoot, which doesn't authenticate
    SMS callbacks at all), so existing channels keep working untouched.
    """
    from app.domains.sms_bandwidth.incoming import (
        _resolve_channel,
        process_bandwidth_webhook,
    )

    resolved = await _resolve_channel(session, phone_number=phone_number)
    if resolved is not None:
        cfg = resolved[0].provider_config or {}
        wh_user = cfg.get("webhook_user")
        wh_pass = cfg.get("webhook_pass")
        if wh_user and wh_pass and not verify_basic_auth(
            request.headers.get("Authorization"),
            str(wh_user),
            str(wh_pass),
        ):
            raise ChatwootHTTPException(
                status_code=401,
                detail={"error": "Invalid credentials"},
            )

    try:
        payload = await request.json()
    except Exception:
        return {}

    try:
        await process_bandwidth_webhook(
            session,
            payload=payload,
            phone_number=phone_number,
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "bandwidth.webhook.process_failed phone=%s", phone_number
        )

    return {}


__all__ = ["router"]
