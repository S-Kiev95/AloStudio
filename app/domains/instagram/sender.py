"""Instagram DM outbound — text via Graph API.

Ported from:
  reference/chatwoot/app/services/instagram/messenger/send_on_instagram_service.rb

Sends an outgoing :class:`Message` on a ``Channel::Instagram`` (the
direct-IG-login variant) inbox by POSTing to
``graph.facebook.com/<vN>/me/messages`` with the channel's
``access_token`` as a query parameter.

5e.4 scope:
  * Plain text messages.
  * Stamps Meta's returned ``message_id`` on ``messages.source_id``
    so 5e.3's read-event processor can match against it.

Deferred:
  * Attachments — needs Phase 10 storage.
  * ``HUMAN_AGENT`` tag toggle — same as 5d, gated by an
    installation feature flag (Phase 9 admin config).
  * ``appsecret_proof`` HMAC signing — production hardening
    (Phase 9).
  * The legacy IG-via-FB-page send path
    (``Channel::FacebookPage.instagram_id``) — sub-phase 5e.6.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.conversations.models import Message
from app.domains.inboxes.models import InstagramChannel

log = logging.getLogger(__name__)


def _api_url(channel: InstagramChannel) -> str:
    """``https://graph.facebook.com/<vN>/me/messages?access_token=<channel>``."""
    settings = get_settings()
    base = "https://graph.facebook.com"
    return (
        f"{base}/{settings.facebook_api_version}/me/messages"
        f"?access_token={channel.access_token}"
    )


async def send_text_message_instagram(
    session: AsyncSession,
    *,
    channel: InstagramChannel,
    message: Message,
    to_igsid: str,
) -> bool:
    """POST a text message to Meta's IG Graph endpoint.

    Returns ``True`` on success, ``False`` on transport / 4xx / 5xx
    (logged but never raised — same contract as the FB + WhatsApp
    senders). On success ``message.source_id`` is stamped with the
    Meta message id.
    """
    if not channel.access_token:
        log.warning(
            "instagram.send.skip reason=missing_access_token channel_id=%s",
            channel.id,
        )
        return False
    if not to_igsid:
        log.warning(
            "instagram.send.skip reason=missing_igsid channel_id=%s message_id=%s",
            channel.id,
            message.id,
        )
        return False

    body: dict[str, Any] = {
        "recipient": {"id": to_igsid},
        "message": {"text": message.content or ""},
    }
    url = _api_url(channel)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "instagram.send.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return False
    if resp.status_code >= 400:
        log.warning(
            "instagram.send.api_error channel_id=%s status=%s body=%s",
            channel.id,
            resp.status_code,
            resp.text[:500],
        )
        return False
    try:
        payload = resp.json()
    except ValueError:
        return False
    mid = payload.get("message_id") if isinstance(payload, dict) else None
    if mid:
        message.source_id = str(mid)
        session.add(message)
        await session.flush()
    log.info(
        "instagram.send.ok channel_id=%s message_id=%s mid=%s",
        channel.id,
        message.id,
        mid,
    )
    return True


__all__ = ["send_text_message_instagram"]
