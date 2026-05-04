"""WhatsApp 360dialog API outbound — text messages.

Ported from:
  reference/chatwoot/app/services/whatsapp/providers/whatsapp_360_dialog_service.rb

Sends an outgoing :class:`Message` on a ``Channel::Whatsapp`` (provider
``default``) inbox via the 360dialog Cloud API. Same shape as the
Meta Cloud branch but:

  * Auth header is ``D360-API-KEY`` (no ``Bearer`` prefix).
  * Base path comes from ``provider_config['url']`` (Chatwoot stores
    it per-channel because the URL differs by region — sandbox lives
    at ``https://waba-sandbox.360dialog.io/v1`` while prod is
    ``https://waba.360dialog.io/v1``).
  * No ``messaging_product`` field in the body (that's Meta Cloud-only).
  * Stamps the returned message id on ``messages.source_id``.

Reply context is supported via the same
``content_attributes.in_reply_to_external_id`` convention as Cloud —
360dialog accepts the ``context.message_id`` field shape too.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Message
from app.domains.inboxes.models import WhatsappChannel

log = logging.getLogger(__name__)


def _api_base(channel: WhatsappChannel) -> str:
    """Per-channel base URL — Rails stores it under provider_config.

    Falls back to the production endpoint if the agent didn't set it
    explicitly. The sandbox endpoint
    (``https://waba-sandbox.360dialog.io/v1``) is meant for testing
    only and the agent is expected to set it via provider_config.
    """
    cfg = channel.provider_config or {}
    if isinstance(cfg, dict):
        url = cfg.get("url")
        if url:
            return str(url).rstrip("/")
    return "https://waba.360dialog.io/v1"


def _api_headers(channel: WhatsappChannel) -> dict[str, str]:
    cfg = channel.provider_config or {}
    api_key = cfg.get("api_key") if isinstance(cfg, dict) else None
    return {
        "D360-API-KEY": str(api_key or ""),
        "Content-Type": "application/json",
    }


def _reply_context(message: Message) -> dict[str, Any] | None:
    """Same ``context.message_id`` shape Meta Cloud uses — 360dialog
    accepts it too."""
    ca = message.content_attributes or {}
    if not isinstance(ca, dict):
        return None
    reply_to = ca.get("in_reply_to_external_id")
    if not reply_to:
        return None
    return {"message_id": str(reply_to)}


async def send_text_message_360dialog(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    message: Message,
    to_phone: str,
) -> bool:
    """Send a text message via 360dialog.

    Returns True on success, False on transport / 4xx / 5xx (logged
    but never raised — same contract as the Cloud sender).

    On success ``message.source_id`` is set to the message id
    360dialog returned in the ``messages[0].id`` field.
    """
    cfg = channel.provider_config or {}
    if not isinstance(cfg, dict) or not cfg.get("api_key"):
        log.warning(
            "whatsapp.send.360d.skip reason=missing_api_key channel_id=%s",
            channel.id,
        )
        return False

    body: dict[str, Any] = {
        "to": to_phone,
        "type": "text",
        "text": {"body": message.content or ""},
    }
    ctx = _reply_context(message)
    if ctx is not None:
        body["context"] = ctx

    url = f"{_api_base(channel)}/messages"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=_api_headers(channel), json=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "whatsapp.send.360d.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return False

    if resp.status_code >= 400:
        log.warning(
            "whatsapp.send.360d.api_error channel_id=%s status=%s body=%s",
            channel.id,
            resp.status_code,
            resp.text[:500],
        )
        return False

    try:
        payload = resp.json()
    except ValueError:
        log.warning(
            "whatsapp.send.360d.bad_json channel_id=%s body=%s",
            channel.id,
            resp.text[:500],
        )
        return False

    # 360dialog success shape (v1):
    #   {"messages": [{"id": "gBE..."}]}
    # — same key as Cloud, ID format differs (gB... vs wamid.HBg...).
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list) or not messages:
        log.warning(
            "whatsapp.send.360d.no_message_id channel_id=%s body=%s",
            channel.id,
            payload,
        )
        return False
    msg_id = messages[0].get("id") if isinstance(messages[0], dict) else None
    if msg_id:
        message.source_id = str(msg_id)
        session.add(message)
        await session.flush()
    log.info(
        "whatsapp.send.360d.ok channel_id=%s message_id=%s remote_id=%s",
        channel.id,
        message.id,
        msg_id,
    )
    return True


__all__ = ["send_text_message_360dialog"]
