"""WhatsApp Cloud API outbound — text messages.

Ported from:
  reference/chatwoot/app/services/whatsapp/providers/whatsapp_cloud_service.rb
  reference/chatwoot/app/services/whatsapp/providers/base_service.rb

Sends an outgoing :class:`Message` on a ``Channel::Whatsapp`` (provider
``whatsapp_cloud``) inbox via Meta's Graph API. Stamps the WAMID
returned by Meta on ``messages.source_id`` so:

  * Status webhooks (sent / delivered / read / failed) can match
    against it (5c.3's status processor).
  * The next inbound from the same contact threads onto the same
    conversation via the existing ContactInbox.

5c.4 scope:
  * Plain text messages.
  * Reply-context (``context.message_id``) when the agent's message
    has ``content_attributes.in_reply_to_external_id`` set — Chatwoot
    uses this for "quoted reply" UX.

Deferred to 5c.6:
  * Attachments — needs media-upload via Meta Graph API + Phase 10
    storage.
  * Templates — needs the message-template sync + parameter
    substitution path.
  * Interactive (button / list) sends.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Attachment, Message
from app.domains.inboxes.models import WhatsappChannel

# Our attachment file_type → the WhatsApp message ``type`` (else document).
_WA_MEDIA_TYPE = {"image": "image", "audio": "audio", "video": "video"}

log = logging.getLogger(__name__)


# Mirrors Rails' ``ENV.fetch('WHATSAPP_CLOUD_BASE_URL', 'https://graph.facebook.com')``.
def _api_base() -> str:
    return os.environ.get(
        "WHATSAPP_CLOUD_BASE_URL", "https://graph.facebook.com"
    )


# Rails picks v13.0 for the phone-id path. We mirror — Meta keeps
# accepting older Graph versions on a long deprecation tail, and
# matching the reference makes diff-against-prod easier.
_PHONE_ID_API_VERSION = "v13.0"


def _phone_id_path(channel: WhatsappChannel) -> str:
    cfg = channel.provider_config or {}
    pid = cfg.get("phone_number_id") if isinstance(cfg, dict) else None
    return f"{_api_base()}/{_PHONE_ID_API_VERSION}/{pid}"


def _api_headers(channel: WhatsappChannel) -> dict[str, str]:
    cfg = channel.provider_config or {}
    api_key = cfg.get("api_key") if isinstance(cfg, dict) else None
    return {
        "Authorization": f"Bearer {api_key or ''}",
        "Content-Type": "application/json",
    }


def _reply_context(message: Message) -> dict[str, Any] | None:
    """Mirror ``whatsapp_reply_context``.

    Picks the WAMID we want Meta to thread under from
    ``content_attributes.in_reply_to_external_id``. Returns ``None``
    when no reply context is set so we can drop the key entirely
    rather than send ``context: null`` (Meta accepts both, but the
    reference omits it).
    """
    ca = message.content_attributes or {}
    if not isinstance(ca, dict):
        return None
    reply_to = ca.get("in_reply_to_external_id")
    if not reply_to:
        return None
    return {"message_id": str(reply_to)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def send_text_message_cloud(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    message: Message,
    to_phone: str,
) -> bool:
    """Send a text message via Meta's Cloud API.

    Returns ``True`` on success, ``False`` on a 4xx / 5xx / network
    error (logged, never raised — the caller mustn't break the
    request because Graph is flaky).

    Side effects on success:
      * ``message.source_id`` set to the WAMID Meta returned.
      * Message persisted via the caller's session.
    """
    cfg = channel.provider_config or {}
    if not isinstance(cfg, dict) or not cfg.get("api_key") or not cfg.get(
        "phone_number_id"
    ):
        log.warning(
            "whatsapp.send.skip reason=missing_provider_config channel_id=%s",
            channel.id,
        )
        return False

    body: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message.content or ""},
    }
    ctx = _reply_context(message)
    if ctx is not None:
        body["context"] = ctx

    url = f"{_phone_id_path(channel)}/messages"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url, headers=_api_headers(channel), json=body
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "whatsapp.send.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return False

    if resp.status_code >= 400:
        log.warning(
            "whatsapp.send.api_error channel_id=%s status=%s body=%s",
            channel.id,
            resp.status_code,
            resp.text[:500],
        )
        return False

    try:
        payload = resp.json()
    except ValueError:
        log.warning(
            "whatsapp.send.bad_json channel_id=%s body=%s",
            channel.id,
            resp.text[:500],
        )
        return False

    # Meta's success shape:
    #   {"messaging_product":"whatsapp","contacts":[{"wa_id":"..."}],
    #    "messages":[{"id":"wamid.HBg..."}]}
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list) or not messages:
        log.warning(
            "whatsapp.send.no_message_id channel_id=%s body=%s",
            channel.id,
            payload,
        )
        return False
    wamid = messages[0].get("id") if isinstance(messages[0], dict) else None
    if wamid:
        message.source_id = str(wamid)
        session.add(message)
        await session.flush()
    log.info(
        "whatsapp.send.ok channel_id=%s message_id=%s wamid=%s",
        channel.id,
        message.id,
        wamid,
    )
    return True


async def send_media_message_cloud(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    message: Message,
    to_phone: str,
    attachment: Attachment,
) -> bool:
    """Send an image/audio/video/document attachment via the Cloud API.

    Two hops: upload the bytes to Meta's ``/media`` for a media id, then send
    a ``type=<media>`` message referencing it. The bytes come from our object
    store (fetched server-side). Best-effort — logs + returns False on any
    failure, stamping the WAMID on success. The message content rides along as
    the caption (except audio, which Meta doesn't caption).
    """
    from app.core.storage import signed_read_url

    cfg = channel.provider_config or {}
    if (
        not isinstance(cfg, dict)
        or not cfg.get("api_key")
        or not cfg.get("phone_number_id")
    ):
        log.warning(
            "whatsapp.send_media.skip reason=missing_config channel_id=%s",
            channel.id,
        )
        return False
    if not attachment.external_url:
        return False

    auth = {"Authorization": _api_headers(channel)["Authorization"]}
    wa_type = _WA_MEDIA_TYPE.get(attachment.file_type_str, "document")
    filename = f"{message.id or 'file'}.{attachment.extension or 'bin'}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            blob = await client.get(signed_read_url(attachment.external_url))
            blob.raise_for_status()
            data = blob.content
            content_type = (
                blob.headers.get("content-type") or "application/octet-stream"
            )
            upload = await client.post(
                f"{_phone_id_path(channel)}/media",
                headers=auth,
                data={"messaging_product": "whatsapp", "type": content_type},
                files={"file": (filename, data, content_type)},
            )
            if upload.status_code >= 400:
                log.warning(
                    "whatsapp.send_media.upload_error channel_id=%s status=%s "
                    "body=%s",
                    channel.id,
                    upload.status_code,
                    upload.text[:300],
                )
                return False
            media_id = (upload.json() or {}).get("id")
            if not media_id:
                return False

            type_content: dict[str, Any] = {"id": media_id}
            if wa_type != "audio" and message.content:
                type_content["caption"] = message.content
            if wa_type == "document":
                type_content["filename"] = filename
            body: dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": to_phone,
                "type": wa_type,
                wa_type: type_content,
            }
            reply = _reply_context(message)
            if reply is not None:
                body["context"] = reply
            resp = await client.post(
                f"{_phone_id_path(channel)}/messages",
                headers=_api_headers(channel),
                json=body,
            )
    except (httpx.RequestError, httpx.TimeoutException, ValueError) as exc:
        log.warning(
            "whatsapp.send_media.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return False

    if resp.status_code >= 400:
        log.warning(
            "whatsapp.send_media.api_error channel_id=%s status=%s body=%s",
            channel.id,
            resp.status_code,
            resp.text[:300],
        )
        return False
    try:
        payload = resp.json()
    except ValueError:
        return False
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list) or not messages:
        return False
    wamid = messages[0].get("id") if isinstance(messages[0], dict) else None
    if wamid:
        message.source_id = str(wamid)
        session.add(message)
        await session.flush()
    log.info(
        "whatsapp.send_media.ok channel_id=%s message_id=%s type=%s wamid=%s",
        channel.id,
        message.id,
        wa_type,
        wamid,
    )
    return True


__all__ = ["send_media_message_cloud", "send_text_message_cloud"]
