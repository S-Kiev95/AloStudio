"""Bandwidth SMS outbound — text via Bandwidth's messaging API.

Ported from:
  reference/chatwoot/app/models/channel/sms.rb (send_message,
    send_to_bandwidth)
  reference/chatwoot/app/services/sms/send_on_sms_service.rb

POSTs to ``messaging.bandwidth.com/api/v2/users/<account_id>/messages``
with HTTP Basic auth ``(api_token, api_secret)`` from
``provider_config``. The body carries ``to``, ``from``, ``text``,
``applicationId``.

5f.4 scope:
  * Plain SMS text messages.
  * Stamps Bandwidth's returned ``id`` on ``messages.source_id``.

Deferred:
  * MMS (``media`` array) — Phase 10 storage.
  * Delivery status callbacks (Bandwidth ``message-delivered`` /
    ``message-failed`` events) — sub-phase follow-up.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Message
from app.domains.inboxes.models import SmsChannel

log = logging.getLogger(__name__)

_BANDWIDTH_API_BASE = "https://messaging.bandwidth.com/api/v2"


def _credentials(channel: SmsChannel) -> tuple[str, str, str, str] | None:
    """Pluck ``(account_id, api_token, api_secret, application_id)``
    from ``provider_config``. Returns None if any value is missing.
    """
    cfg = channel.provider_config or {}
    if not isinstance(cfg, dict):
        return None
    account_id = cfg.get("account_id")
    api_token = cfg.get("api_token")
    api_secret = cfg.get("api_secret")
    application_id = cfg.get("application_id")
    if not all((account_id, api_token, api_secret, application_id)):
        return None
    return (
        str(account_id),
        str(api_token),
        str(api_secret),
        str(application_id),
    )


async def send_sms_bandwidth(
    session: AsyncSession,
    *,
    channel: SmsChannel,
    message: Message,
    to_phone: str,
) -> bool:
    """POST a text SMS to Bandwidth's messaging API.

    Returns True on success, False on transport / 4xx / 5xx
    (logged but never raised). On success ``message.source_id`` is
    stamped with Bandwidth's message id.
    """
    creds = _credentials(channel)
    if creds is None:
        log.warning(
            "bandwidth.send.skip reason=missing_provider_config "
            "channel_id=%s",
            channel.id,
        )
        return False
    account_id, api_token, api_secret, application_id = creds

    if not to_phone:
        log.warning(
            "bandwidth.send.skip reason=missing_to channel_id=%s message_id=%s",
            channel.id,
            message.id,
        )
        return False

    body: dict[str, Any] = {
        "to": [to_phone],
        "from": channel.phone_number,
        "text": message.content or "",
        "applicationId": application_id,
    }
    url = f"{_BANDWIDTH_API_BASE}/users/{account_id}/messages"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url, json=body, auth=(api_token, api_secret)
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "bandwidth.send.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return False
    if resp.status_code >= 400:
        log.warning(
            "bandwidth.send.api_error channel_id=%s status=%s body=%s",
            channel.id,
            resp.status_code,
            resp.text[:500],
        )
        return False
    try:
        payload = resp.json()
    except ValueError:
        return False
    bw_id = payload.get("id") if isinstance(payload, dict) else None
    if bw_id:
        message.source_id = str(bw_id)
        session.add(message)
        await session.flush()
    log.info(
        "bandwidth.send.ok channel_id=%s message_id=%s id=%s",
        channel.id,
        message.id,
        bw_id,
    )
    return True


__all__ = ["send_sms_bandwidth"]
