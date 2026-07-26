"""Facebook Messenger webhook payload processor.

Ported from:
  reference/chatwoot/app/builders/messages/facebook/message_builder.rb
  reference/chatwoot/app/builders/messages/messenger/message_builder.rb
  reference/chatwoot/app/jobs/webhooks/facebook_events_job.rb
  reference/chatwoot/app/jobs/webhooks/facebook_delivery_job.rb

Walks Meta's Messenger webhook payload + creates Contact +
ContactInbox + Conversation + Message rows. The payload shape:

    {
      "object": "page",
      "entry": [
        {
          "id": "<PAGE_ID>",
          "messaging": [
            {
              "sender":    {"id": "<PSID>"},
              "recipient": {"id": "<PAGE_ID>"},
              "timestamp": <ms>,
              "message":   {"mid": "<MID>", "text": "..."}
            },
            ...
          ]
        }
      ]
    }

5d.3 scope:
  * Text messages.
  * ``message.is_echo`` — a page admin replied via the FB Messenger
    app. We mirror Chatwoot: stamp the message as ``outgoing`` with
    no agent attribution (sender_id = None) so the dashboard knows
    "this came from outside Chatwoot".
  * Delivery / read events (``messaging.delivery`` / ``.read``)
    update the corresponding outbound message status — same as
    Chatwoot's ``Webhooks::FacebookDeliveryJob``.
  * Idempotent on Meta's ``mid`` via ``messages.source_id``.

Deferred to later phases:
  * Attachments — needs Phase 10 storage.
  * Postback / quick_reply / get_started / referral events.
  * Standby + handover protocol (multi-app routing).
  * Reactions.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_STATUS_DELIVERED,
    MESSAGE_STATUS_READ,
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
    CHANNEL_TYPE_FACEBOOK,
    FacebookPage,
    Inbox,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Page resolution
# ---------------------------------------------------------------------------
async def _resolve_page(
    session: AsyncSession, *, page_id: str
) -> tuple[FacebookPage, Inbox] | None:
    """Look up the FacebookPage + Inbox for a given page_id.

    Returns ``None`` for unknown pages so the caller drops the payload
    silently — Meta delivers webhooks to every app subscribed to a
    page, so a foreign event for a page we don't manage is a normal
    occurrence, not an error.
    """
    channel = (
        await session.exec(
            select(FacebookPage).where(FacebookPage.page_id == page_id)
        )
    ).first()
    if channel is None:
        return None
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_FACEBOOK,
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
    psid: str,
) -> Contact:
    """Find a contact by Facebook PSID via its ContactInbox; create
    one if the PSID is new.

    The PSID is page-scoped so we can't lookup by ``contacts.identifier``
    directly — we go through ContactInbox.source_id instead. Rails
    does the same via ``ContactInboxWithContactBuilder``.
    """
    existing = (
        await session.exec(
            select(Contact)
            .join(ContactInbox, ContactInbox.contact_id == Contact.id)
            .where(
                Contact.account_id == account_id,
                ContactInbox.source_id == psid,
            )
        )
    ).first()
    if existing is not None:
        return existing

    placeholder = (
        f"facebook-{psid[-6:]}" if len(psid) >= 6 else f"facebook-{psid}"
    )
    contact = Contact(account_id=account_id, name=placeholder)
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
    mint a new one. Mirrors Chatwoot — Messenger threads are durable
    so one PSID stays on one conversation across reopens.
    """
    latest = (
        await session.exec(
            select(Conversation)
            .where(Conversation.contact_inbox_id == contact_inbox.id)
            .order_by(Conversation.id.desc())
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
# Status events (delivery / read)
# ---------------------------------------------------------------------------
async def _process_delivery_event(
    session: AsyncSession,
    *,
    account_id: int,
    event: dict[str, Any],
    new_status: int,
) -> list[Message]:
    """Update outbound messages whose mids appear in the event.

    Messenger's delivery + read events carry a ``mids`` array — every
    message id covered by the event. We update each one, capping at
    100 mids per event to keep the SQL reasonable (real events ship
    1-5 mids).
    """
    delivery = event.get("delivery") or event.get("read")
    if not isinstance(delivery, dict):
        return []
    mids = delivery.get("mids") or []
    if not isinstance(mids, list) or not mids:
        return []
    out: list[Message] = []
    for mid in mids[:100]:
        msg = (
            await session.exec(
                select(Message).where(
                    Message.account_id == account_id,
                    Message.source_id == str(mid),
                )
            )
        ).first()
        if msg is None:
            continue
        msg.status = new_status
        session.add(msg)
        await session.flush()
        out.append(msg)
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def process_facebook_webhook(
    session: AsyncSession,
    *,
    payload: dict[str, Any],
) -> list[Message]:
    """Convert one Messenger webhook payload to Message rows.

    Returns the list of messages created or updated. Empty list is
    fine (status-only update for a known mid, unknown page,
    duplicate mid, etc).
    """
    if (payload or {}).get("object") != "page":
        return []
    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        return []

    out: list[Message] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        page_id = str(entry.get("id") or "")
        if not page_id:
            continue
        resolved = await _resolve_page(session, page_id=page_id)
        if resolved is None:
            continue
        channel, inbox = resolved

        for event in entry.get("messaging") or []:
            if not isinstance(event, dict):
                continue
            # Delivery / read events first.
            if "delivery" in event:
                out.extend(
                    await _process_delivery_event(
                        session,
                        account_id=channel.account_id,
                        event=event,
                        new_status=MESSAGE_STATUS_DELIVERED,
                    )
                )
                continue
            if "read" in event:
                out.extend(
                    await _process_delivery_event(
                        session,
                        account_id=channel.account_id,
                        event=event,
                        new_status=MESSAGE_STATUS_READ,
                    )
                )
                continue

            message_block = event.get("message")
            if not isinstance(message_block, dict):
                continue
            msg = await _process_message_event(
                session,
                channel=channel,
                inbox=inbox,
                event=event,
                message_block=message_block,
            )
            if msg is not None:
                out.append(msg)

    return out


async def _process_message_event(
    session: AsyncSession,
    *,
    channel: FacebookPage,
    inbox: Inbox,
    event: dict[str, Any],
    message_block: dict[str, Any],
) -> Message | None:
    """Insert (or skip-as-duplicate) one message event."""
    mid = message_block.get("mid")
    if not mid:
        return None

    is_echo = bool(message_block.get("is_echo"))
    sender_block = event.get("sender") or {}
    recipient_block = event.get("recipient") or {}

    # For echoes the PSID is the recipient (the contact); for normal
    # incoming messages it's the sender.
    psid = (
        recipient_block.get("id")
        if is_echo
        else sender_block.get("id")
    )
    psid = str(psid or "")
    if not psid:
        return None

    # Idempotent: skip if we've ingested this mid before.
    already = (
        await session.exec(
            select(Message.id).where(
                Message.account_id == channel.account_id,
                Message.source_id == str(mid),
            )
        )
    ).first()
    if already is not None:
        log.info("facebook.inbound.skip reason=duplicate mid=%s", mid)
        return None

    contact = await _find_or_create_contact(
        session, account_id=channel.account_id, psid=psid
    )
    contact_inbox = await ContactInboxBuilder(
        session=session,
        contact=contact,
        inbox=inbox,
        source_id=psid,
    ).perform()
    conversation = await _find_or_create_conversation(
        session, contact_inbox=contact_inbox
    )

    body = str(message_block.get("text") or "")
    message_type = "outgoing" if is_echo else "incoming"

    try:
        msg = await create_message(
            session,
            conversation=conversation,
            params=_MessageBuilderParams(
                content=body,
                message_type=message_type,
                source_id=str(mid),
            ),
            user_id=None,
        )
    except Exception:
        log.exception("facebook.inbound.create_message_failed mid=%s", mid)
        return None
    return msg


__all__ = ["process_facebook_webhook"]
