"""Twilio webhook surface — ``POST /twilio/callback``.

Twilio's webhook payload arrives as
``application/x-www-form-urlencoded`` (or ``multipart/form-data``
when MMS media is attached). FastAPI's ``Request.form()`` handles
both, returning a flat ``FormData`` we coerce to a dict before
passing to the processor.

Anchors:
  reference/chatwoot/app/controllers/twilio/callback_controller.rb
  reference/chatwoot/config/routes.rb (namespace :twilio
    -> resources :callback, only: [:create])

The endpoint always 200s — Rails returns ``head :no_content``
(204), but Twilio accepts any 2xx and we shape the response as
``{}`` so the wire body is well-formed JSON for tooling that
inspects it. Twilio retries on 5xx so we want to break the retry
loop on every malformed / unknown payload.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session

router = APIRouter(
    tags=["twilio-webhooks"],
)


@router.post("/twilio/callback")
async def twilio_receive(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Receive a Twilio SMS webhook.

    Always returns 200 — see module docstring.
    """
    try:
        form = await request.form()
    except Exception:  # noqa: BLE001
        return {}

    params: dict[str, Any] = {key: form[key] for key in form}

    from app.domains.twilio.incoming import process_twilio_webhook

    try:
        await process_twilio_webhook(session, params=params)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception(
            "twilio.webhook.process_failed"
        )

    return {}


__all__ = ["router"]
