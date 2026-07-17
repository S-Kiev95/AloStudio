"""Instagram DM outbound — text + attachments via Graph API.

Ported from:
  reference/chatwoot/app/services/instagram/base_send_service.rb
  reference/chatwoot/app/services/instagram/messenger/send_on_instagram_service.rb

Sends an outgoing :class:`Message` on a ``Channel::Instagram`` inbox by
POSTing to ``graph.facebook.com/<vN>/me/messages`` with the channel's
``access_token`` as a query parameter.

Attachments follow ``BaseSendService#send_attachments`` — Meta takes **one
attachment per message**, so each becomes its own send — with one deliberate
divergence: Rails hands Meta a public URL to pull from
(``payload: {url: attachment.download_url}``) because its send runs in an
after-commit background job. Ours runs inside the create-message
transaction, so Meta's fetch races the commit and 404s. We upload the bytes
to ``/me/message_attachments`` for a reusable ``attachment_id`` instead,
which also keeps the object store private and mirrors the WhatsApp Cloud
sender.

Deferred:
  * ``HUMAN_AGENT`` tag toggle — gated by an installation feature flag
    (Phase 9 admin config).
  * ``appsecret_proof`` HMAC signing — production hardening (Phase 9).
  * The legacy IG-via-FB-page send path
    (``Channel::FacebookPage.instagram_id``) — sub-phase 5e.6.
"""

from __future__ import annotations

import json
import logging
import mimetypes
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.storage import signed_read_url
from app.domains.conversations.models import Attachment, Message
from app.domains.inboxes.models import InstagramChannel

log = logging.getLogger(__name__)

# Rails' ``attachment_type``: Meta's Send API only accepts these four, so an
# ig_post / share / story_mention we forward degrades to ``file``.
_IG_SEND_TYPES = frozenset({"image", "audio", "video", "file"})

# Uploads carry the whole file — a DM video is far slower than a text POST.
_UPLOAD_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _graph_base() -> str:
    return f"https://graph.facebook.com/{get_settings().facebook_api_version}"


def _api_url(channel: InstagramChannel) -> str:
    """``https://graph.facebook.com/<vN>/me/messages?access_token=<channel>``."""
    return f"{_graph_base()}/me/messages?access_token={channel.access_token}"


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


async def _upload_attachment(
    channel: InstagramChannel, attachment: Attachment
) -> str | None:
    """Push the blob to ``/me/message_attachments`` → reusable
    ``attachment_id``, or ``None`` on any failure (logged).

    Reads the object server-side (the store is internal-only) and hands the
    bytes to Meta, rather than Rails' public-URL pull — see the module
    docstring for why.
    """
    send_type = _send_attachment_type(attachment.file_type_str)
    ext = attachment.extension or "bin"
    filename = f"attachment.{ext}"
    content_type = (
        mimetypes.guess_type(filename)[0] or "application/octet-stream"
    )
    try:
        async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT) as client:
            blob = await client.get(signed_read_url(attachment.external_url or ""))
            blob.raise_for_status()
            resp = await client.post(
                f"{_graph_base()}/me/message_attachments",
                params={"access_token": channel.access_token},
                data={
                    "message": json.dumps(
                        {
                            "attachment": {
                                "type": send_type,
                                "payload": {"is_reusable": True},
                            }
                        }
                    )
                },
                files={"filedata": (filename, blob.content, content_type)},
            )
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        log.warning(
            "instagram.send.upload_transport_error channel_id=%s err=%s",
            channel.id,
            type(exc).__name__,
        )
        return None
    if resp.status_code >= 400:
        log.warning(
            "instagram.send.upload_error channel_id=%s status=%s body=%s",
            channel.id,
            resp.status_code,
            resp.text[:500],
        )
        return None
    try:
        payload = resp.json()
    except ValueError:
        return None
    attachment_id = (
        payload.get("attachment_id") if isinstance(payload, dict) else None
    )
    if not attachment_id:
        log.warning(
            "instagram.send.upload_error channel_id=%s reason=no_attachment_id",
            channel.id,
        )
        return None
    return str(attachment_id)


async def send_attachment_message_instagram(
    session: AsyncSession,
    *,
    channel: InstagramChannel,
    message: Message,
    to_igsid: str,
    attachment: Attachment,
) -> bool:
    """Upload one attachment to Meta, then send it by ``attachment_id``."""
    if not _can_send(channel, message, to_igsid):
        return False
    if not attachment.external_url:
        log.warning(
            "instagram.send.skip reason=attachment_without_blob channel_id=%s "
            "message_id=%s",
            channel.id,
            message.id,
        )
        return False

    attachment_id = await _upload_attachment(channel, attachment)
    if attachment_id is None:
        return False

    body: dict[str, Any] = {
        "recipient": {"id": to_igsid},
        "message": {
            "attachment": {
                "type": _send_attachment_type(attachment.file_type_str),
                "payload": {"attachment_id": attachment_id},
            }
        },
    }
    return await _post_send(
        session, channel=channel, message=message, body=body
    )


__all__ = [
    "send_attachment_message_instagram",
    "send_text_message_instagram",
]
