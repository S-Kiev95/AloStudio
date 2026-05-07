"""Twilio SMS outbound — text via Twilio's REST API.

Ported from:
  reference/chatwoot/app/services/twilio/send_on_twilio_service.rb
  reference/chatwoot/app/models/channel/twilio_sms.rb (send_message,
    send_message_from)

Twilio's REST API uses HTTP Basic auth. We POST to
``api.twilio.com/2010-04-01/Accounts/<account_sid>/Messages.json``
with form-encoded body containing ``To`` + ``Body`` plus EITHER
``From`` (phone-number routing) OR ``MessagingServiceSid`` (pool
routing — same precedence Rails uses in
``Channel::TwilioSms#send_message_from``).

5f.3 scope:
  * Plain SMS text messages.
  * Stamps Twilio's returned ``sid`` on ``messages.source_id`` for
    delivery-status webhook matching (delivery callbacks ship later).

Deferred:
  * MMS attachments (``MediaUrl``) — Phase 10 storage.
  * ``status_callback`` URL — needs a public-facing callback URL
    we don't have until deploy + the matching webhook handler
    (sub-phase 5f.7).
  * Twilio's WhatsApp medium — sub-phase 5f.6 (the ``To`` field
    becomes ``whatsapp:+<number>`` and the ``From`` likewise).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Message
from app.domains.inboxes.models import TwilioSmsChannel

log = logging.getLogger(__name__)

# Rails uses ``Twilio::REST::Client`` which targets api.twilio.com/2010-04-01.
# Bumping this version is a Twilio-side decision — they keep
# 2010-04-01 indefinitely for back-compat.
_TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


def _send_message_from(channel: TwilioSmsChannel) -> dict[str, str]:
    """Mirror ``Channel::TwilioSms#send_message_from``.

    MessagingServiceSid takes precedence — Twilio uses the service
    to pick a sender from a pool. Falls back to the channel's
    ``phone_number`` otherwise.
    """
    if channel.messaging_service_sid:
        return {"MessagingServiceSid": channel.messaging_service_sid}
    if channel.phone_number:
        return {"From": channel.phone_number}
    return {}


def _basic_auth(channel: TwilioSmsChannel) -> tuple[str, str]:
    """Pick the Basic-auth pair.

    Rails:
      ``Twilio::REST::Client.new(api_key_sid, auth_token, account_sid)``
      when api_key_sid is set, else
      ``Twilio::REST::Client.new(account_sid, auth_token)``.

    HTTP Basic auth uses the first arg as username + the second as
    password. We pass (account_sid, auth_token) by default, and
    (api_key_sid, auth_token) when the api_key path is configured.
    """
    if channel.api_key_sid:
        return (channel.api_key_sid, channel.auth_token)
    return (channel.account_sid, channel.auth_token)


async def send_sms_twilio(
    session: AsyncSession,
    *,
    channel: TwilioSmsChannel,
    message: Message,
    to_phone: str,
) -> bool:
    """POST a text SMS to Twilio's REST API.

    Returns ``True`` on success, ``False`` on transport / 4xx / 5xx
    (logged but never raised — same contract as the FB / IG / WA
    senders). On success ``message.source_id`` is stamped with
    Twilio's message SID.
    """
    if not channel.account_sid or not channel.auth_token:
        log.warning(
            "twilio.send.skip reason=missing_credentials channel_id=%s",
            channel.id,
        )
        return False
    if not to_phone:
        log.warning(
            "twilio.send.skip reason=missing_to channel_id=%s message_id=%s",
            channel.id,
            message.id,
        )
        return False

    from_block = _send_message_from(channel)
    if not from_block:
        log.warning(
            "twilio.send.skip reason=missing_from_or_msvc channel_id=%s",
            channel.id,
        )
        return False

    body: dict[str, str] = {
        "To": to_phone,
        "Body": message.content or "",
        **from_block,
    }
    url = (
        f"{_TWILIO_API_BASE}/Accounts/{channel.account_sid}/Messages.json"
    )
    auth = _basic_auth(channel)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data=body, auth=auth)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "twilio.send.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return False
    if resp.status_code >= 400:
        log.warning(
            "twilio.send.api_error channel_id=%s status=%s body=%s",
            channel.id,
            resp.status_code,
            resp.text[:500],
        )
        return False
    try:
        payload = resp.json()
    except ValueError:
        return False
    sid = payload.get("sid") if isinstance(payload, dict) else None
    if sid:
        message.source_id = str(sid)
        session.add(message)
        await session.flush()
    log.info(
        "twilio.send.ok channel_id=%s message_id=%s sid=%s",
        channel.id,
        message.id,
        sid,
    )
    return True


__all__ = ["send_sms_twilio"]
