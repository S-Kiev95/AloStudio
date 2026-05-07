"""Telegram webhook payload processor.

Ported from:
  reference/chatwoot/app/services/telegram/incoming_message_service.rb
  reference/chatwoot/app/services/telegram/param_helpers.rb
  reference/chatwoot/app/jobs/webhooks/telegram_events_job.rb

Telegram delivers updates to a single webhook URL with the bot token
in the path. The payload shape (Bot API ``Update`` object):

    {
      "update_id": 123,
      "message": {
        "message_id": 456,
        "from":  {"id": <user_id>, "first_name": "...", "username": "..."},
        "chat":  {"id": <chat_id>, "type": "private", ...},
        "date":  1700000000,
        "text":  "...",
        "reply_to_message": {"message_id": 100, ...}  # optional
      }
    }

5g.2 scope:
  * Plain text messages from private chats only (Chatwoot
    intentionally drops group chats).
  * Idempotent on Telegram's ``message_id`` via
    ``messages.source_id``.
  * ``reply_to_message`` -> stamps the previous message id under
    ``content_attributes.in_reply_to_external_id`` for Phase 9 UI.

Deferred:
  * Group chats — Chatwoot doesn't support them either.
  * Attachments (photo, document, voice, video, sticker) — Phase
    10 storage.
  * Callback queries (inline-button replies).
  * Telegram Business updates (``business_connection_id``).
  * ``edit_message_text`` (edits arrive as ``edited_message``).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams as _MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.inboxes.models import (
    CHANNEL_TYPE_TELEGRAM,
    Inbox,
    TelegramChannel,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel resolution
# ---------------------------------------------------------------------------
async def _resolve_channel(
    session: AsyncSession, *, bot_token: str
) -> tuple[TelegramChannel, Inbox] | None:
    channel = (
        await session.exec(
            select(TelegramChannel).where(
                TelegramChannel.bot_token == bot_token
            )
        )
    ).first()
    if channel is None:
        return None
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_TELEGRAM,
                Inbox.channel_id == channel.id,
            )
        )
    ).first()
    if inbox is None:
        return None
    return channel, inbox


# ---------------------------------------------------------------------------
# Contact + conversation
# ---------------------------------------------------------------------------
def _placeholder_name(message_block: dict[str, Any]) -> str:
    """Mirror Rails ``contact_attributes`` — first_name + last_name
    fall back to username, then to a Telegram-id-derived
    placeholder."""
    user = message_block.get("from") or {}
    if not isinstance(user, dict):
        user = {}
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    full = f"{first} {last}".strip()
    if full:
        return full
    if user.get("username"):
        return f"@{user['username']}"
    uid = user.get("id")
    return f"telegram-{uid}" if uid is not None else "telegram-user"


async def _find_or_create_contact(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: str,
    name: str,
) -> Contact:
    """Find a contact by Telegram user id via its ContactInbox; create
    one if the user is new.

    Telegram user ids are page-scoped (technically bot-scoped) so we
    look up via ContactInbox.source_id rather than a Contact-level
    field. Same shape as the FB / IG inbound resolvers.
    """
    existing = (
        await session.exec(
            select(Contact)
            .join(ContactInbox, ContactInbox.contact_id == Contact.id)
            .where(
                Contact.account_id == account_id,
                ContactInbox.source_id == user_id,
            )
        )
    ).first()
    if existing is not None:
        return existing
    contact = Contact(account_id=account_id, name=name)
    session.add(contact)
    await session.flush()
    await session.refresh(contact)
    return contact


async def _find_or_create_conversation(
    session: AsyncSession,
    *,
    contact_inbox: ContactInbox,
    chat_id: int | str,
) -> Conversation:
    """Re-use the most recent conversation on this ContactInbox; mint
    a new one with chat_id stamped in additional_attributes (the
    sender reads it back for ``sendMessage``).
    """
    latest = (
        await session.exec(
            select(Conversation)
            .where(Conversation.contact_inbox_id == contact_inbox.id)
            .order_by(Conversation.id.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
    ).first()
    if latest is not None:
        # Backfill the chat_id when missing (legacy conversation row).
        attrs = dict(latest.additional_attributes or {})
        if not attrs.get("chat_id"):
            attrs["chat_id"] = chat_id
            latest.additional_attributes = attrs
            session.add(latest)
            await session.flush()
        return latest
    return await create_conversation(
        session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(
            additional_attributes={"chat_id": chat_id},
        ),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def process_telegram_webhook(
    session: AsyncSession,
    *,
    bot_token: str,
    payload: dict[str, Any],
) -> Message | None:
    """Convert one Telegram ``Update`` payload to a Message row.

    Returns the inserted message or ``None`` for skipped cases
    (group chats, missing message block, duplicate update, unknown
    bot token).
    """
    if not isinstance(payload, dict):
        return None

    message_block = payload.get("message")
    if not isinstance(message_block, dict):
        # 5g.2 only handles plain ``message`` updates. Edits +
        # callback_query + business updates land in follow-ups.
        return None

    chat = message_block.get("chat") or {}
    if not isinstance(chat, dict) or chat.get("type") != "private":
        # Group / channel / supergroup chats — Chatwoot drops these.
        return None

    user = message_block.get("from") or {}
    if not isinstance(user, dict):
        return None
    user_id = user.get("id")
    if user_id is None:
        return None

    chat_id = chat.get("id")
    if chat_id is None:
        return None

    text = message_block.get("text") or message_block.get("caption") or ""
    tg_message_id = message_block.get("message_id")
    if tg_message_id is None:
        return None

    resolved = await _resolve_channel(session, bot_token=bot_token)
    if resolved is None:
        return None
    channel, inbox = resolved

    source_id = str(tg_message_id)
    already = (
        await session.exec(
            select(Message.id).where(
                Message.account_id == channel.account_id,
                Message.source_id == source_id,
            )
        )
    ).first()
    if already is not None:
        log.info(
            "telegram.inbound.skip reason=duplicate message_id=%s",
            source_id,
        )
        return None

    contact = await _find_or_create_contact(
        session,
        account_id=channel.account_id,
        user_id=str(user_id),
        name=_placeholder_name(message_block),
    )
    contact_inbox = await ContactInboxBuilder(
        session=session,
        contact=contact,
        inbox=inbox,
        source_id=str(user_id),
    ).perform()
    conversation = await _find_or_create_conversation(
        session, contact_inbox=contact_inbox, chat_id=chat_id
    )

    # Reply-to: Telegram sends the parent message under
    # ``reply_to_message``. We stamp the parent's id on
    # content_attributes so the outbound path can pass
    # ``reply_to_message_id`` to sendMessage.
    content_attrs: dict[str, Any] = {}
    reply_to = message_block.get("reply_to_message")
    if isinstance(reply_to, dict) and reply_to.get("message_id") is not None:
        content_attrs["in_reply_to_external_id"] = str(
            reply_to["message_id"]
        )

    try:
        msg = await create_message(
            session,
            conversation=conversation,
            params=_MessageBuilderParams(
                content=str(text),
                message_type="incoming",
                content_attributes=content_attrs or None,
                source_id=source_id,
            ),
            user_id=None,
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "telegram.inbound.create_message_failed message_id=%s",
            source_id,
        )
        return None
    return msg


__all__ = ["process_telegram_webhook"]
