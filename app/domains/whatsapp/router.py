"""WhatsApp webhook surface — ``/webhooks/whatsapp/{phone_number}``.

Two endpoints share the path:

  * ``GET`` — Meta's verification handshake. Echoes back
    ``hub.challenge`` when ``hub.verify_token`` matches the channel's
    stored ``webhook_verify_token``. 401 with the error envelope
    otherwise. Mirrors Rails' ``MetaTokenVerifyConcern``.

  * ``POST`` — receives inbound message payloads from Meta (Cloud) or
    360dialog. Phase 5c.2 just acknowledges the payload (and returns
    200 so Meta doesn't retry); the actual ingest happens in 5c.3
    via ``process_cloud_webhook``.

Anchors:
  reference/chatwoot/app/controllers/webhooks/whatsapp_controller.rb
  reference/chatwoot/app/controllers/concerns/meta_token_verify_concern.rb
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    Inbox,
    WhatsappChannel,
)

router = APIRouter(
    prefix="/webhooks/whatsapp",
    tags=["whatsapp-webhooks"],
)


async def _resolve_channel(
    session: AsyncSession, *, phone_number: str
) -> tuple[WhatsappChannel, Inbox]:
    """Load the WhatsappChannel + Inbox by phone_number.

    Raises 404 with ``{"error": "Phone number not found"}`` when no
    channel matches — Rails uses ``ActiveRecord::RecordNotFound`` here
    which ActionController auto-renders as 404.
    """
    channel = (
        await session.exec(
            select(WhatsappChannel).where(
                WhatsappChannel.phone_number == phone_number
            )
        )
    ).first()
    if channel is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Phone number not found"},
        )
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_WHATSAPP,
                Inbox.channel_id == channel.id,
            )
        )
    ).first()
    if inbox is None:
        # Defensive: orphaned channel row -> same 404 as missing channel.
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Phone number not found"},
        )
    return channel, inbox


@router.get("/{phone_number}")
async def whatsapp_verify(
    phone_number: Annotated[str, Path()],
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
    hub_verify_token: Annotated[
        str | None, Query(alias="hub.verify_token")
    ] = None,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Meta verification handshake.

    Returns the raw ``hub.challenge`` value (not JSON-wrapped) when the
    token matches — that's what Meta's docs require. FastAPI's
    response auto-detection serializes a plain string as JSON which
    technically still works for Meta, but we'd rather echo the
    challenge verbatim.
    """
    channel, _inbox = await _resolve_channel(
        session, phone_number=phone_number
    )
    if (
        hub_verify_token is None
        or channel.webhook_verify_token is None
        or hub_verify_token != channel.webhook_verify_token
    ):
        raise ChatwootHTTPException(
            status_code=401,
            detail={"error": "Error; wrong verify token"},
        )
    # Meta requires the challenge echoed back verbatim. Return as a
    # plain string — FastAPI's default response will JSON-encode it,
    # which Meta accepts (the actual handshake just compares the body
    # value).
    return hub_challenge or ""


@router.post("/{phone_number}")
async def whatsapp_receive(
    phone_number: Annotated[str, Path()],
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Receive a WhatsApp webhook payload.

    5c.2 just acknowledges the request — actual ingest happens in
    5c.3 once :func:`process_cloud_webhook` is wired here. We resolve
    the channel up-front so unknown numbers 404 fast (matches Rails'
    ``Channel::Whatsapp.find_by(phone_number:)`` lookup).
    """
    channel, inbox = await _resolve_channel(
        session, phone_number=phone_number
    )
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        # Malformed JSON — Rails just acks (Meta retries on 5xx, so a
        # bad payload that we can't parse should still 200 to break
        # the retry loop).
        return {"status": "ok"}

    # 5c.3 will dispatch into the per-provider parser here. Keep the
    # branch shape so the wiring is a one-line change.
    from app.domains.whatsapp.incoming_cloud import process_cloud_webhook

    if channel.provider == "whatsapp_cloud":
        try:
            await process_cloud_webhook(
                session, channel=channel, inbox=inbox, payload=payload
            )
        except Exception:  # noqa: BLE001
            # The processor logs internally — we always 200 so Meta
            # doesn't retry a payload we already partially handled.
            import logging

            logging.getLogger(__name__).exception(
                "whatsapp.webhook.process_failed channel_id=%s", channel.id
            )

    return {"status": "ok"}


__all__ = ["router"]
