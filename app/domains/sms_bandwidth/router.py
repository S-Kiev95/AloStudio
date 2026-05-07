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

from app.core.db import get_session

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
    """
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return {}

    from app.domains.sms_bandwidth.incoming import process_bandwidth_webhook

    try:
        await process_bandwidth_webhook(
            session,
            payload=payload,
            phone_number=phone_number,
        )
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception(
            "bandwidth.webhook.process_failed phone=%s", phone_number
        )

    return {}


__all__ = ["router"]
