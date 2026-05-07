"""Telegram outbound — text via Bot API.

Ported from:
  reference/chatwoot/app/services/telegram/send_on_telegram_service.rb
  reference/chatwoot/app/models/channel/telegram.rb
    (send_message, message_request)

POSTs to ``https://api.telegram.org/bot<bot_token>/sendMessage``
with JSON body ``{chat_id, text}`` plus optional
``reply_to_message_id`` from
``content_attributes.in_reply_to_external_id``. The bot token
lives in the URL (no auth header — Telegram's REST convention).

5g.3 scope:
  * Plain text messages.
  * ``reply_to_message_id`` for quoted-reply UX.
  * Stamps Telegram's returned ``message_id`` on
    ``messages.source_id`` so the inbound dedup works on edits.

Deferred:
  * Attachments (sendPhoto / sendDocument / sendVoice / sendVideo)
    — Phase 10 storage + a separate SendAttachmentsService port.
  * Telegram Business mode (``business_connection_id`` body field) —
    Phase 9 follow-up.
  * Inline keyboards (``reply_markup``) — Phase 8 bot infra.
  * MarkdownV2 escaping — Chatwoot uses a TelegramRenderer that
    sanitises markdown; defer to a later sub-phase.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Conversation, Message
from app.domains.inboxes.models import TelegramChannel

log = logging.getLogger(__name__)


def _api_url(channel: TelegramChannel) -> str:
    return f"https://api.telegram.org/bot{channel.bot_token}/sendMessage"


def _reply_to_message_id(message: Message) -> int | None:
    """Mirror ``Channel::Telegram#reply_to_message_id``.

    Reads ``content_attributes.in_reply_to_external_id`` and coerces
    to int (Telegram's ``message_id`` is a Bot API integer).
    """
    ca = message.content_attributes or {}
    if not isinstance(ca, dict):
        return None
    raw = ca.get("in_reply_to_external_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def send_text_telegram(
    session: AsyncSession,
    *,
    channel: TelegramChannel,
    message: Message,
    chat_id: int | str,
) -> bool:
    """POST a text message to Telegram's Bot API.

    Returns ``True`` on success, ``False`` on transport / 4xx / 5xx
    (logged but never raised). On success ``message.source_id`` is
    stamped with Telegram's message_id.
    """
    if not channel.bot_token:
        log.warning(
            "telegram.send.skip reason=missing_bot_token channel_id=%s",
            channel.id,
        )
        return False
    if not chat_id:
        log.warning(
            "telegram.send.skip reason=missing_chat_id channel_id=%s message_id=%s",
            channel.id,
            message.id,
        )
        return False

    body: dict[str, Any] = {
        "chat_id": chat_id,
        "text": message.content or "",
    }
    reply_to = _reply_to_message_id(message)
    if reply_to is not None:
        body["reply_to_message_id"] = reply_to

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_api_url(channel), json=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "telegram.send.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return False
    if resp.status_code >= 400:
        log.warning(
            "telegram.send.api_error channel_id=%s status=%s body=%s",
            channel.id,
            resp.status_code,
            resp.text[:500],
        )
        return False
    try:
        payload = resp.json()
    except ValueError:
        return False

    # Telegram success shape: ``{"ok": true, "result": {"message_id": N, ...}}``.
    if not isinstance(payload, dict) or not payload.get("ok"):
        log.warning(
            "telegram.send.bot_error channel_id=%s body=%s",
            channel.id,
            payload,
        )
        return False
    result = payload.get("result")
    mid = result.get("message_id") if isinstance(result, dict) else None
    if mid is not None:
        message.source_id = str(mid)
        session.add(message)
        await session.flush()
    log.info(
        "telegram.send.ok channel_id=%s message_id=%s tg_message_id=%s",
        channel.id,
        message.id,
        mid,
    )
    return True


def chat_id_for(conversation: Conversation) -> int | str | None:
    """Mirror ``Channel::Telegram#chat_id`` —
    ``conversation.additional_attributes['chat_id']``.

    Returns ``None`` when the conversation row predates the 5g.2
    ingest (no chat_id stamped); the caller short-circuits.
    """
    attrs = conversation.additional_attributes or {}
    if not isinstance(attrs, dict):
        return None
    chat_id = attrs.get("chat_id")
    if chat_id is None:
        return None
    return chat_id


__all__ = ["chat_id_for", "send_text_telegram"]
