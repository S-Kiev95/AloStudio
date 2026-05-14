"""WebhookListener — delivers dispatcher events to account-configured
HTTP receivers.

Ported from:
  reference/chatwoot/app/listeners/webhook_listener.rb
  reference/chatwoot/app/jobs/webhook_job.rb (delivery contract)

For each dispatcher event we know how to map (see :data:`_EVENT_MAP`),
the listener:
  1. Resolves the subject (conversation / message / contact) from the
     payload + maps to the canonical webhook event name.
  2. Looks up every account-type Webhook whose ``subscriptions``
     includes that event name.
  3. POSTs the standard envelope to each Webhook with the
     ``X-Chatwoot-Signature`` HMAC header.

Failure isolation: per-webhook try/except so a single bad receiver
doesn't fail siblings or the request cycle.

Phase 8.3 scope:
  * conversation_created / conversation_updated / conversation_status_changed
  * message_created
  * Activity messages are skipped (mirrors ``webhook_sendable?``).

Deferred:
  * contact_created / contact_updated / inbox_created / inbox_updated —
    not yet dispatched as ``CONTACT_*`` / ``INBOX_*`` events on our
    side (Phase 4b's listener inventory mentions them as TODO).
  * conversation_typing_on / off — needs the typing payload. Not
    parity-critical for v4.13.0 webhook receivers.
  * webwidget_triggered / message_updated.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.agent_bots.listener import (
    _build_conversation_webhook_body,
    _build_message_webhook_body,
    _is_webhook_sendable,
)
from app.domains.conversations import events as ev
from app.domains.conversations.models import Conversation, Message
from app.domains.webhooks.models import Webhook
from app.domains.webhooks.service import webhooks_subscribed_to

log = logging.getLogger(__name__)

# Dispatcher event name → ``Webhook.subscriptions`` event name.
_EVENT_MAP: dict[str, str] = {
    ev.CONVERSATION_CREATED: "conversation_created",
    ev.CONVERSATION_UPDATED: "conversation_updated",
    ev.CONVERSATION_STATUS_CHANGED: "conversation_status_changed",
    ev.MESSAGE_CREATED: "message_created",
}


async def fan_out_to_webhooks(
    session: AsyncSession, event_name: str, **payload: Any
) -> None:
    subscribed_name = _EVENT_MAP.get(event_name)
    if subscribed_name is None:
        return

    account_id, body = _resolve_subject(subscribed_name, payload)
    if account_id is None or body is None:
        return

    webhooks = await webhooks_subscribed_to(
        session, account_id=account_id, event_name=subscribed_name
    )
    if not webhooks:
        return
    for hook in webhooks:
        await _deliver(hook, body)


def _resolve_subject(
    subscribed_name: str, payload: dict[str, Any]
) -> tuple[int | None, dict[str, Any] | None]:
    """Build (account_id, webhook_body) for the event.

    Returns ``(None, None)`` when the payload doesn't carry the
    expected subject (defensive — listeners must never raise)."""
    if subscribed_name == "message_created":
        message = payload.get("message")
        if not isinstance(message, Message):
            return None, None
        if not _is_webhook_sendable(message):
            return None, None
        conversation = message.conversation
        if not isinstance(conversation, Conversation):
            return None, None
        body = _build_message_webhook_body(
            conversation=conversation,
            message=message,
            event_name=subscribed_name,
        )
        return conversation.account_id, body

    # Conversation-level events.
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return None, None
    changed_attributes = payload.get("changed_attributes")
    body = _build_conversation_webhook_body(
        conversation=conversation,
        event_name=subscribed_name,
        changed_attributes=changed_attributes,
    )
    return conversation.account_id, body


def _sign(body_bytes: bytes, secret: str | None) -> str:
    if not secret:
        return ""
    return hmac.new(
        secret.encode("utf-8"), body_bytes, hashlib.sha256
    ).hexdigest()


async def _deliver(hook: Webhook, payload: dict[str, Any]) -> None:
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Chatwoot-Delivery": str(uuid.uuid4()),
        "X-Chatwoot-Signature": _sign(body_bytes, hook.secret),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                hook.url, content=body_bytes, headers=headers
            )
        if resp.status_code >= 400:
            log.warning(
                "webhook.delivery.non_2xx webhook_id=%s status=%s",
                hook.id,
                resp.status_code,
            )
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        log.warning(
            "webhook.delivery.transport_error webhook_id=%s err=%s",
            hook.id,
            exc,
        )


__all__ = ["fan_out_to_webhooks"]
