"""Bandwidth SMS webhook payload processor.

Ported from:
  reference/chatwoot/app/services/sms/incoming_message_service.rb
  reference/chatwoot/app/jobs/webhooks/sms_events_job.rb
  reference/chatwoot/app/controllers/webhooks/sms_controller.rb

Bandwidth's webhook payload is a JSON array — one element per event
(inbound message, delivery callback, etc). Each element has a
``type`` discriminator (``message-received``, ``message-delivered``,
``message-failed``, ...). 5f.4 handles ``message-received`` only;
delivery callbacks ship later.

Payload shape (single inbound):

    [
      {
        "type": "message-received",
        "message": {
          "id":          "<bandwidth-id>",
          "from":        "+15559998888",
          "to":          ["+15551234567"],
          "text":        "...",
          "applicationId": "...",
          "time":        "2026-05-06T12:34:56Z"
        }
      }
    ]

The ``to`` array always contains exactly one number (Bandwidth's
multi-recipient feature uses a different webhook path that
Chatwoot doesn't subscribe to).
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
    create_conversation,
    create_message,
)
from app.domains.conversations.service import (
    MessageBuilderParams as _MessageBuilderParams,
)
from app.domains.inboxes.models import (
    CHANNEL_TYPE_SMS,
    Inbox,
    SmsChannel,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel resolution
# ---------------------------------------------------------------------------
async def _resolve_channel(
    session: AsyncSession, *, phone_number: str
) -> tuple[SmsChannel, Inbox] | None:
    channel = (
        await session.exec(
            select(SmsChannel).where(SmsChannel.phone_number == phone_number)
        )
    ).first()
    if channel is None:
        return None
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_SMS,
                Inbox.channel_id == channel.id,
            )
        )
    ).first()
    if inbox is None:
        return None
    return channel, inbox


# ---------------------------------------------------------------------------
# Contact / conversation
# ---------------------------------------------------------------------------
async def _find_or_create_contact(
    session: AsyncSession,
    *,
    account_id: int,
    phone_number: str,
) -> Contact:
    existing = (
        await session.exec(
            select(Contact).where(
                Contact.account_id == account_id,
                Contact.phone_number == phone_number,
            )
        )
    ).first()
    if existing is not None:
        return existing
    contact = Contact(
        account_id=account_id,
        phone_number=phone_number,
        name=phone_number,
    )
    session.add(contact)
    await session.flush()
    await session.refresh(contact)
    return contact


async def _find_or_create_conversation(
    session: AsyncSession,
    *,
    contact_inbox: ContactInbox,
) -> Conversation:
    latest = (
        await session.exec(
            select(Conversation)
            .where(Conversation.contact_inbox_id == contact_inbox.id)
            .order_by(Conversation.id.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
    ).first()
    if latest is not None:
        return latest
    return await create_conversation(
        session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def process_bandwidth_webhook(
    session: AsyncSession,
    *,
    payload: list[dict[str, Any]] | dict[str, Any],
    phone_number: str,
) -> list[Message]:
    """Convert one Bandwidth webhook payload to Message rows.

    ``phone_number`` comes from the URL path
    (``/webhooks/sms/<phone_number>``); we use it to resolve the
    channel up-front so a payload that doesn't match the URL drops
    silently. Bandwidth's array can carry multiple events (rare in
    practice — usually one) so we walk it and dispatch.
    """
    resolved = await _resolve_channel(session, phone_number=phone_number)
    if resolved is None:
        return []
    channel, inbox = resolved

    events = payload if isinstance(payload, list) else [payload]
    out: list[Message] = []

    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") != "message-received":
            # delivery / failure / direction=out callbacks ship later.
            continue
        message_block = event.get("message")
        if not isinstance(message_block, dict):
            continue

        bw_id = message_block.get("id")
        if not bw_id:
            continue
        already = (
            await session.exec(
                select(Message.id).where(
                    Message.account_id == channel.account_id,
                    Message.source_id == str(bw_id),
                )
            )
        ).first()
        if already is not None:
            log.info("bandwidth.inbound.skip reason=duplicate id=%s", bw_id)
            continue

        from_phone = str(message_block.get("from") or "")
        if not from_phone:
            continue
        body = str(message_block.get("text") or "")

        contact = await _find_or_create_contact(
            session,
            account_id=channel.account_id,
            phone_number=from_phone,
        )
        contact_inbox = await ContactInboxBuilder(
            session=session,
            contact=contact,
            inbox=inbox,
            source_id=from_phone,
        ).perform()
        conversation = await _find_or_create_conversation(
            session, contact_inbox=contact_inbox
        )
        try:
            msg = await create_message(
                session,
                conversation=conversation,
                params=_MessageBuilderParams(
                    content=body,
                    message_type="incoming",
                    source_id=str(bw_id),
                ),
                user_id=None,
            )
        except Exception:
            log.exception(
                "bandwidth.inbound.create_message_failed id=%s", bw_id
            )
            continue
        out.append(msg)

    return out


__all__ = ["process_bandwidth_webhook"]
