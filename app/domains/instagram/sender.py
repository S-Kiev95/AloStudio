"""Instagram DM outbound — text + attachments via Graph API.

Ported from:
  reference/chatwoot/app/services/instagram/base_send_service.rb
  reference/chatwoot/app/services/instagram/messenger/send_on_instagram_service.rb

Sends an outgoing :class:`Message` on a ``Channel::Instagram`` inbox by
POSTing to ``graph.facebook.com/<vN>/me/messages`` with the channel's
``access_token`` as a query parameter.

Attachments mirror ``BaseSendService#send_attachments``: Meta takes **one
attachment per message**, so each becomes its own send, and it downloads
``payload.url`` from its own side — which is why we hand it a signed public
link (:func:`~app.domains.conversations.attachments_router.public_attachment_url`)
rather than the internal object-store URL.

Deferred:
  * ``HUMAN_AGENT`` tag toggle — gated by an installation feature flag
    (Phase 9 admin config).
  * ``appsecret_proof`` HMAC signing — production hardening (Phase 9).
  * The legacy IG-via-FB-page send path
    (``Channel::FacebookPage.instagram_id``) — sub-phase 5e.6.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.conversations.models import Attachment, Message
from app.domains.inboxes.models import InstagramChannel

log = logging.getLogger(__name__)

# Rails' ``attachment_type``: Meta's Send API only accepts these four, so an
# ig_post / share / story_mention we forward degrades to ``file``.
_IG_SEND_TYPES = frozenset({"image", "audio", "video", "file"})


def _api_url(channel: InstagramChannel) -> str:
    """``https://graph.facebook.com/<vN>/me/messages?access_token=<channel>``."""
    settings = get_settings()
    base = "https://graph.facebook.com"
    return (
        f"{base}/{settings.facebook_api_version}/me/messages"
        f"?access_token={channel.access_token}"
    )


def _send_attachment_type(file_type: str) -> str:
    """Rails' ``attachment_type`` — anything Meta doesn't know is a file."""
    return file_type if file_type in _IG_SEND_TYPES else "file"


async def _post_send(
    session: AsyncSession,
    *,
    channel: InstagramChannel,
    message: Message,
    body: dict[str, Any],
) -> bool:
    """POST one send to Meta and stamp the returned mid.

    Returns ``True`` on success, ``False`` on transport / 4xx / 5xx (logged
    but never raised — same contract as the FB + WhatsApp senders). Rails'
    ``process_response`` stamps ``source_id`` on every successful send, so a
    message with attachments ends up carrying the last mid.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_api_url(channel), json=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "instagram.send.transport_error channel_id=%s err=%s",
            channel.id,
            type(exc).__name__,
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


def _can_send(channel: InstagramChannel, message: Message, to_igsid: str) -> bool:
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
    return True


async def send_text_message_instagram(
    session: AsyncSession,
    *,
    channel: InstagramChannel,
    message: Message,
    to_igsid: str,
) -> bool:
    """POST a text message to Meta's IG Graph endpoint."""
    if not _can_send(channel, message, to_igsid):
        return False
    body: dict[str, Any] = {
        "recipient": {"id": to_igsid},
        "message": {"text": message.content or ""},
    }
    return await _post_send(
        session, channel=channel, message=message, body=body
    )


async def send_attachment_message_instagram(
    session: AsyncSession,
    *,
    channel: InstagramChannel,
    message: Message,
    to_igsid: str,
    attachment: Attachment,
) -> bool:
    """POST one attachment to Meta's IG Graph endpoint.

    Meta downloads ``payload.url`` itself, so the attachment is handed over
    as a signed, expiring public link — the object store is internal-only and
    the dashboard's proxy needs a session.
    """
    if not _can_send(channel, message, to_igsid):
        return False
    if attachment.id is None or not attachment.external_url:
        log.warning(
            "instagram.send.skip reason=attachment_without_blob channel_id=%s "
            "message_id=%s",
            channel.id,
            message.id,
        )
        return False

    # Imported lazily: the router imports models that import this module.
    from app.domains.conversations.attachments_router import (
        public_attachment_url,
    )

    body: dict[str, Any] = {
        "recipient": {"id": to_igsid},
        "message": {
            "attachment": {
                "type": _send_attachment_type(attachment.file_type_str),
                "payload": {"url": public_attachment_url(attachment.id)},
            }
        },
    }
    return await _post_send(
        session, channel=channel, message=message, body=body
    )


async def send_private_reply_instagram(
    *,
    channel: InstagramChannel,
    ig_comment_id: str,
    text: str,
) -> bool:
    """Answer a public comment with a private message.

    Meta's "private reply" is the same ``/me/messages`` send the DM path
    uses, addressed by ``comment_id`` instead of a user id — the person's
    IGSID is not known until they are in a thread, and this is what opens
    that thread. It is the mechanic behind "comentá X y te lo paso": the
    link arrives in the inbox rather than under the post, and the reply
    lands as a real conversation the team can continue.

    Deliberately does not go through ``_post_send``: there is no local
    Message row to stamp a mid onto. Never raises — a failed send is
    logged and reported, and the caller has already marked the comment so
    it will not be retried into a duplicate.
    """
    body: dict[str, Any] = {
        "recipient": {"comment_id": ig_comment_id},
        "message": {"text": text},
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_api_url(channel), json=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "instagram.private_reply.transport_error comment=%s err=%s",
            ig_comment_id,
            type(exc).__name__,
        )
        return False
    if resp.status_code >= 400:
        log.warning(
            "instagram.private_reply.failed comment=%s status=%s body=%s",
            ig_comment_id,
            resp.status_code,
            resp.text[:300],
        )
        return False
    return True


__all__ = [
    "send_attachment_message_instagram",
    "send_private_reply_instagram",
    "send_text_message_instagram",
]
