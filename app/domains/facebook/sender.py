"""Facebook Messenger outbound — text via Graph API.

Ported from:
  reference/chatwoot/app/services/facebook/send_on_facebook_service.rb

Sends an outgoing :class:`Message` on a ``Channel::FacebookPage``
inbox by POSTing to ``graph.facebook.com/<vN>/me/messages`` with the
page access token as a query parameter (Meta's Messenger API uses
the query-param form rather than a Bearer header for this endpoint).

5d.4 scope:
  * Plain text messages.
  * ``messaging_type: MESSAGE_TAG`` + ``tag: ACCOUNT_UPDATE`` —
    Chatwoot's default. Lets the agent reply outside the 24-hour
    customer-service window for the conversation. The tag toggles to
    ``HUMAN_AGENT`` when the installation flag
    ``ENABLE_MESSENGER_CHANNEL_HUMAN_AGENT`` is set; we keep
    ACCOUNT_UPDATE always for 5d.4.
  * Stamps Meta's returned ``message_id`` on ``messages.source_id``
    so 5d.3's delivery / read events can match against it.

Deferred to later phases:
  * Attachments (image / file / video / sticker) — needs Phase 10
    storage.
  * ``input_select`` (quick_replies) — interactive UI.
  * ``HUMAN_AGENT`` toggle — installation config in Phase 9.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.conversations.models import Message
from app.domains.inboxes.models import FacebookPage

log = logging.getLogger(__name__)


def _api_url(channel: FacebookPage) -> str:
    """``https://graph.facebook.com/<vN>/me/messages?access_token=<page>``."""
    settings = get_settings()
    base = "https://graph.facebook.com"
    return (
        f"{base}/{settings.facebook_api_version}/me/messages"
        f"?access_token={channel.page_access_token}"
    )


async def send_text_message_facebook(
    session: AsyncSession,
    *,
    channel: FacebookPage,
    message: Message,
    to_psid: str,
) -> bool:
    """POST a text message to Meta's Messenger Graph endpoint.

    Returns ``True`` on success, ``False`` on transport / 4xx / 5xx
    (logged but never raised — same contract as the WhatsApp
    senders). On success ``message.source_id`` is stamped with the
    Meta message id.
    """
    if not channel.page_access_token:
        log.warning(
            "facebook.send.skip reason=missing_page_access_token channel_id=%s",
            channel.id,
        )
        return False
    if not to_psid:
        log.warning(
            "facebook.send.skip reason=missing_psid channel_id=%s message_id=%s",
            channel.id,
            message.id,
        )
        return False

    body: dict[str, Any] = {
        "recipient": {"id": to_psid},
        "message": {"text": message.content or ""},
        "messaging_type": "MESSAGE_TAG",
        "tag": "ACCOUNT_UPDATE",
    }
    url = _api_url(channel)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "facebook.send.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return False
    if resp.status_code >= 400:
        log.warning(
            "facebook.send.api_error channel_id=%s status=%s body=%s",
            channel.id,
            resp.status_code,
            resp.text[:500],
        )
        return False
    try:
        payload = resp.json()
    except ValueError:
        return False
    # Meta's success shape: {"recipient_id": "PSID", "message_id": "mid.x"}
    mid = payload.get("message_id") if isinstance(payload, dict) else None
    if mid:
        message.source_id = str(mid)
        session.add(message)
        await session.flush()
    log.info(
        "facebook.send.ok channel_id=%s message_id=%s mid=%s",
        channel.id,
        message.id,
        mid,
    )
    return True


__all__ = ["send_text_message_facebook"]
