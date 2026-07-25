"""Twilio SMS webhook payload processor.

Ported from:
  reference/chatwoot/app/services/twilio/incoming_message_service.rb
  reference/chatwoot/app/jobs/webhooks/twilio_events_job.rb

Twilio webhooks arrive as ``application/x-www-form-urlencoded``
(or ``multipart/form-data`` when MMS media is attached). FastAPI
unwraps both into a flat dict; we accept the dict directly so tests
can construct fixtures without going through the HTTP layer.

Channel resolution order mirrors Rails:
  1. ``MessagingServiceSid`` (when the channel was set up with a
     Messaging Service rather than a single from-number).
  2. ``(AccountSid, To)`` — a Twilio account can own multiple
     numbers; the ``To`` field tells us which one received the SMS.

5f.2 scope:
  * Plain SMS text messages.
  * Idempotent on Twilio's ``SmsSid`` (== ``MessageSid``) via
    ``messages.source_id``.

Deferred:
  * MMS attachments (``MediaUrl0..N`` + ``MediaContentType0..N``)
    — Phase 10 storage.
  * Twilio's WhatsApp medium — sub-phase 5f.6.
  * Location messages.
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
    CHANNEL_TYPE_TWILIO_SMS,
    TWILIO_MEDIUM_SMS,
    Inbox,
    TwilioSmsChannel,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel resolution
# ---------------------------------------------------------------------------
async def _resolve_channel(
    session: AsyncSession,
    *,
    params: dict[str, Any],
) -> tuple[TwilioSmsChannel, Inbox] | None:
    """Mirror Rails' two-step lookup:

      1. ``MessagingServiceSid`` (when set).
      2. ``(AccountSid, To)`` fallback.

    Both clauses scope to ``medium=sms`` — the WhatsApp medium has
    a different resolver path that ships in 5f.6.
    """
    msvc = params.get("MessagingServiceSid")
    account_sid = params.get("AccountSid")
    to = params.get("To")

    channel: TwilioSmsChannel | None = None
    if msvc:
        channel = (
            await session.exec(
                select(TwilioSmsChannel).where(
                    TwilioSmsChannel.messaging_service_sid == str(msvc),
                    TwilioSmsChannel.medium == TWILIO_MEDIUM_SMS,
                )
            )
        ).first()
    if channel is None and account_sid and to:
        channel = (
            await session.exec(
                select(TwilioSmsChannel).where(
                    TwilioSmsChannel.account_sid == str(account_sid),
                    TwilioSmsChannel.phone_number == str(to),
                    TwilioSmsChannel.medium == TWILIO_MEDIUM_SMS,
                )
            )
        ).first()
    if channel is None:
        log.info(
            "twilio.inbound.channel_not_found account_sid=%s to=%s msvc=%s",
            account_sid,
            to,
            msvc,
        )
        return None
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_TWILIO_SMS,
                Inbox.channel_id == channel.id,
            )
        )
    ).first()
    if inbox is None:
        return None
    return channel, inbox


# ---------------------------------------------------------------------------
# Contact / conversation resolution
# ---------------------------------------------------------------------------
async def _find_or_create_contact(
    session: AsyncSession,
    *,
    account_id: int,
    phone_number: str,
) -> Contact:
    """Find a contact by phone number; create one if new."""
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
        name=phone_number,  # placeholder until the agent renames
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
    """Re-use the most recent conversation on this ContactInbox else
    mint a new one. SMS threads are durable per (number, inbox) — same
    rationale as Messenger / IG (one number == one chat)."""
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
async def process_twilio_webhook(
    session: AsyncSession,
    *,
    params: dict[str, Any],
) -> Message | None:
    """Convert one Twilio webhook payload into a Message row.

    Twilio webhooks deliver one message per HTTP call (unlike Meta's
    batch payloads), so we return a single optional Message instead
    of a list. Empty / unresolved / duplicate cases return None.
    """
    sms_sid = params.get("SmsSid") or params.get("MessageSid")
    body = params.get("Body")
    from_phone = params.get("From")
    if not sms_sid or not from_phone:
        return None

    resolved = await _resolve_channel(session, params=params)
    if resolved is None:
        return None
    channel, inbox = resolved

    # Idempotent on SmsSid.
    already = (
        await session.exec(
            select(Message.id).where(
                Message.account_id == channel.account_id,
                Message.source_id == str(sms_sid),
            )
        )
    ).first()
    if already is not None:
        log.info("twilio.inbound.skip reason=duplicate sms_sid=%s", sms_sid)
        return None

    contact = await _find_or_create_contact(
        session,
        account_id=channel.account_id,
        phone_number=str(from_phone),
    )
    contact_inbox = await ContactInboxBuilder(
        session=session,
        contact=contact,
        inbox=inbox,
        source_id=str(from_phone),
    ).perform()
    conversation = await _find_or_create_conversation(
        session, contact_inbox=contact_inbox
    )

    try:
        msg = await create_message(
            session,
            conversation=conversation,
            params=_MessageBuilderParams(
                content=str(body or ""),
                message_type="incoming",
                source_id=str(sms_sid),
            ),
            user_id=None,
        )
    except Exception:
        log.exception(
            "twilio.inbound.create_message_failed sms_sid=%s", sms_sid
        )
        return None
    return msg


__all__ = ["process_twilio_webhook"]
