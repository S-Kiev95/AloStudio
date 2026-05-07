"""Telegram webhook surface — ``POST /webhooks/telegram/<bot_token>``.

The bot token IS the credential — Telegram requires it in the URL
path so the bot can verify the request actually came from them
(anyone hitting the URL must already know the secret token). No
separate verify-token handshake.

Anchors:
  reference/chatwoot/app/controllers/webhooks/telegram_controller.rb
  reference/chatwoot/config/routes.rb
    (post 'webhooks/telegram/:bot_token')
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session

router = APIRouter(
    tags=["telegram-webhooks"],
)


@router.post("/webhooks/telegram/{bot_token}")
async def telegram_receive(
    bot_token: Annotated[str, Path()],
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Receive a Telegram ``Update`` payload.

    Always 200s — Telegram retries with exponential backoff on
    non-200 responses, so unknown tokens, malformed bodies, and
    group-chat drops must all ack.
    """
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return {}

    if not isinstance(payload, dict):
        return {}

    from app.domains.telegram.incoming import process_telegram_webhook

    try:
        await process_telegram_webhook(
            session,
            bot_token=bot_token,
            payload=payload,
        )
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception(
            "telegram.webhook.process_failed"
        )

    return {}


__all__ = ["router"]
