"""AgentBotListener — relays dispatcher events to the bot's outgoing_url.

Ported from:
  reference/chatwoot/app/listeners/agent_bot_listener.rb
  reference/chatwoot/app/jobs/agent_bots/webhook_job.rb (delivery contract)

Subscribes to the same dispatcher events as Chatwoot's listener.
For each event:
  1. Resolve the bots attached to the conversation's inbox (and the
     bot explicitly assigned via ``assignee_agent_bot_id`` when set).
  2. Build the standard Chatwoot webhook envelope (``event`` +
     conversation/message context).
  3. POST to each bot's ``outgoing_url`` with an
     ``X-Chatwoot-Signature`` header — SHA-256 HMAC of the body bytes
     keyed on the bot's ``secret``.

Skips:
  * Bots without an ``outgoing_url``.
  * ``message.created`` events on activity / template-internal
    messages (mirrors ``message.webhook_sendable?``).

Failure isolation: each POST runs in its own try/except so a single
bad bot endpoint doesn't fail siblings or the request.

Phase 8.2 ships the message_created / conversation_resolved /
conversation_opened / conversation_updated / conversation_status_changed
relays. message_updated and webwidget_triggered defer (the latter
needs the widget's ContactInbox lifecycle event which isn't yet wired).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.agent_bots.models import AgentBot
from app.domains.agent_bots.service import attached_bot_for_inbox
from app.domains.conversations import events as ev
from app.domains.conversations.models import (
    MESSAGE_TYPE_ACTIVITY,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    MESSAGE_TYPE_TEMPLATE,
    Conversation,
    Message,
    conversation_priority_to_str,
    conversation_status_to_str,
    message_type_to_str,
)
from app.domains.webhooks.models import RECEIVER_KIND_AGENT_BOT
from app.workers.deliver_webhook import enqueue_delivery


def _resolve_sender_type(message: Message) -> str | None:
    """Normalize ``Message.sender_type`` to a short string for webhooks.

    Chatwoot's STI yields values like ``User`` / ``Contact`` /
    ``AgentBot`` (and the channel-injected synthetic ``api`` value for
    messages produced by API-channel posts without a user). We emit the
    lowercase form so receivers can branch on a stable contract.
    """
    raw = message.sender_type
    if not raw:
        return None
    lower = raw.lower()
    if lower in {"user", "contact", "agentbot", "agent_bot", "api"}:
        # Normalize ``AgentBot`` → ``agent_bot`` for snake-case parity
        # with the rest of the webhook body.
        if lower == "agentbot":
            return "agent_bot"
        return lower
    return lower

log = logging.getLogger(__name__)

# Dispatcher event name → AgentBot webhook envelope event name.
_EVENT_MAP: dict[str, str] = {
    ev.CONVERSATION_CREATED: "conversation_created",
    ev.CONVERSATION_UPDATED: "conversation_updated",
    ev.CONVERSATION_STATUS_CHANGED: "conversation_status_changed",
    ev.CONVERSATION_OPENED: "conversation_opened",
    ev.CONVERSATION_RESOLVED: "conversation_resolved",
    ev.MESSAGE_CREATED: "message_created",
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def fan_out_to_agent_bots(
    session: AsyncSession, event_name: str, **payload: Any
) -> None:
    """Single entry point called from :func:`broadcast_event`."""
    relay_event_name = _EVENT_MAP.get(event_name)
    if relay_event_name is None:
        return

    if relay_event_name == "message_created":
        message = payload.get("message")
        if not isinstance(message, Message):
            return
        if not _is_webhook_sendable(message):
            return
        conversation = message.conversation
        if not isinstance(conversation, Conversation):
            return
        await _relay_message_event(
            session,
            conversation=conversation,
            message=message,
            event_name=relay_event_name,
        )
        return

    # Conversation-level events.
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return
    changed_attributes = payload.get("changed_attributes")
    await _relay_conversation_event(
        session,
        conversation=conversation,
        event_name=relay_event_name,
        changed_attributes=changed_attributes,
    )


# ---------------------------------------------------------------------------
# Per-event relay helpers
# ---------------------------------------------------------------------------
def _is_webhook_sendable(message: Message) -> bool:
    """Mirror ``Message#webhook_sendable?`` — incoming / outgoing /
    template, but NOT activity."""
    return message.message_type in (
        MESSAGE_TYPE_INCOMING,
        MESSAGE_TYPE_OUTGOING,
        MESSAGE_TYPE_TEMPLATE,
    )


async def _relay_message_event(
    session: AsyncSession,
    *,
    conversation: Conversation,
    message: Message,
    event_name: str,
) -> None:
    bots = await _bots_for(session, conversation=conversation)
    if not bots:
        return
    for bot in bots:
        # ``event_id`` is per-delivery, NOT per-event — each receiver
        # gets its own UUID so retries can be deduped per hook.
        body = _build_message_webhook_body(
            conversation=conversation,
            message=message,
            event_name=event_name,
            event_id=str(uuid.uuid4()),
        )
        await _enqueue_bot_delivery(
            session, bot=bot, body=body, event_name=event_name
        )


async def _relay_conversation_event(
    session: AsyncSession,
    *,
    conversation: Conversation,
    event_name: str,
    changed_attributes: Any,
) -> None:
    bots = await _bots_for(session, conversation=conversation)
    if not bots:
        return
    for bot in bots:
        body = _build_conversation_webhook_body(
            conversation=conversation,
            event_name=event_name,
            changed_attributes=changed_attributes,
            event_id=str(uuid.uuid4()),
        )
        await _enqueue_bot_delivery(
            session, bot=bot, body=body, event_name=event_name
        )


async def _enqueue_bot_delivery(
    session: AsyncSession,
    *,
    bot: AgentBot,
    body: dict[str, Any],
    event_name: str,
) -> None:
    """Push the bot relay onto the ARQ delivery queue (v2.9). Skips
    when the bot has no outgoing_url configured — that mirrors the
    pre-v2.9 inline path."""
    if not bot.outgoing_url:
        return
    await enqueue_delivery(
        session=session,
        account_id=bot.account_id,  # type: ignore[arg-type]
        receiver_kind=RECEIVER_KIND_AGENT_BOT,
        receiver_id=bot.id,
        url=bot.outgoing_url,
        event_name=event_name,
        body=body,
        secret=bot.secret,
    )


async def _bots_for(
    session: AsyncSession,
    *,
    conversation: Conversation,
) -> list[AgentBot]:
    """Mirror ``agent_bots_for(inbox, conversation)``.

    Combine the bot directly assigned to the conversation (via
    ``assignee_agent_bot_id``) with the bot attached to the inbox.
    De-duplicate by id."""
    bots: list[AgentBot] = []
    seen: set[int] = set()

    if conversation.assignee_agent_bot_id is not None:
        direct = await session.get(AgentBot, conversation.assignee_agent_bot_id)
        if direct is not None and direct.id is not None:
            bots.append(direct)
            seen.add(direct.id)

    if conversation.inbox_id is not None:
        inbox_bot = await attached_bot_for_inbox(
            session, inbox_id=conversation.inbox_id
        )
        if inbox_bot is not None and inbox_bot.id is not None and inbox_bot.id not in seen:
            bots.append(inbox_bot)

    return bots


# ---------------------------------------------------------------------------
# Body shape
# ---------------------------------------------------------------------------
def _conversation_webhook_data(conv: Conversation) -> dict[str, Any]:
    """Mirror ``Conversation#webhook_data`` (subset).

    We omit the deeply nested ``meta`` / ``messages`` Chatwoot ships
    on the conversation envelope — bots that need them can re-fetch
    via the standard API. Phase 8 ships the surface most webhooks
    consume in practice (id, status, priority, ids, timestamps).
    """
    return {
        "id": conv.id,
        "account_id": conv.account_id,
        "inbox_id": conv.inbox_id,
        "contact_id": conv.contact_id,
        "assignee_id": conv.assignee_id,
        "team_id": conv.team_id,
        "status": conversation_status_to_str(conv.status),
        "priority": conversation_priority_to_str(conv.priority),
        "display_id": conv.display_id,
        "uuid": str(conv.uuid) if conv.uuid is not None else None,
        "additional_attributes": conv.additional_attributes or {},
        "custom_attributes": conv.custom_attributes or {},
        "created_at": int(conv.created_at.timestamp()) if conv.created_at else None,
    }


def _build_message_webhook_body(
    *,
    conversation: Conversation,
    message: Message,
    event_name: str,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Mirror ``Message#webhook_data`` merged with ``event`` + a v2.7
    ``event_id`` (UUID) that mirrors the ``X-Chatwoot-Delivery`` header
    so receivers can dedupe purely from the body.

    ``sender_type`` (v2.7) is the lowercase STI label — ``user`` /
    ``contact`` / ``agent_bot`` / ``api`` — emitted so receivers can
    branch without an MCP round-trip.
    """
    body: dict[str, Any] = {
        "event": event_name,
        "id": message.id,
        "content": message.content,
        "content_type": message.content_type,
        "message_type": message_type_to_str(message.message_type),
        "sender_type": _resolve_sender_type(message),
        "sender_id": message.sender_id,
        "private": bool(message.private),
        "source_id": message.source_id,
        "content_attributes": message.content_attributes or {},
        "additional_attributes": message.additional_attributes or {},
        "created_at": int(message.created_at.timestamp())
        if message.created_at
        else None,
        "conversation": _conversation_webhook_data(conversation),
    }
    if event_id is not None:
        body["event_id"] = event_id
    return body


def _build_conversation_webhook_body(
    *,
    conversation: Conversation,
    event_name: str,
    changed_attributes: Any,
    event_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "event": event_name,
        **_conversation_webhook_data(conversation),
    }
    if changed_attributes is not None:
        body["changed_attributes"] = changed_attributes
    if event_id is not None:
        body["event_id"] = event_id
    return body


__all__ = ["fan_out_to_agent_bots"]
