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

import logging
import uuid
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.agent_bots.listener import (
    _build_conversation_webhook_body,
    _build_message_webhook_body,
    _is_webhook_sendable,
)
from app.domains.conversations import events as ev
from app.domains.conversations.models import Conversation, Message
from app.domains.webhooks.models import RECEIVER_KIND_WEBHOOK
from app.domains.webhooks.service import webhooks_subscribed_to
from app.workers.deliver_webhook import enqueue_delivery

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

    account_id, builder = _resolve_subject(subscribed_name, payload)
    if account_id is None or builder is None:
        return

    webhooks = await webhooks_subscribed_to(
        session, account_id=account_id, event_name=subscribed_name
    )
    if not webhooks:
        return
    for hook in webhooks:
        # Per-delivery event_id (v2.7) so the same logical event sent
        # to multiple subscribers carries distinct dedupe keys.
        body = builder(event_id=str(uuid.uuid4()))
        # v2.9: enqueue instead of POSTing inline. The ARQ task handles
        # retries + dead-letter; the inline-fallback path (no ARQ pool)
        # delivers once and writes the dead-letter row directly on
        # failure so dev + test envs still see end-to-end behaviour.
        await enqueue_delivery(
            session=session,
            account_id=account_id,
            receiver_kind=RECEIVER_KIND_WEBHOOK,
            receiver_id=hook.id,
            url=hook.url,
            event_name=subscribed_name,
            body=body,
            secret=hook.secret,
        )


# A builder closure here keeps the per-hook ``event_id`` injection clean
# without re-walking the payload for each receiver.
def _resolve_subject(
    subscribed_name: str, payload: dict[str, Any]
) -> tuple[int | None, Any]:
    """Build (account_id, body_builder(event_id) → dict) for the event.

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

        def _build(*, event_id: str) -> dict[str, Any]:
            return _build_message_webhook_body(
                conversation=conversation,
                message=message,
                event_name=subscribed_name,
                event_id=event_id,
            )

        return conversation.account_id, _build

    # Conversation-level events.
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return None, None
    changed_attributes = payload.get("changed_attributes")

    def _build_conv(*, event_id: str) -> dict[str, Any]:
        return _build_conversation_webhook_body(
            conversation=conversation,
            event_name=subscribed_name,
            changed_attributes=changed_attributes,
            event_id=event_id,
        )

    return conversation.account_id, _build_conv


__all__ = ["fan_out_to_webhooks"]
