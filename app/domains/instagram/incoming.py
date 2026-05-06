"""Instagram DM webhook payload processor.

Ported from:
  reference/chatwoot/app/jobs/webhooks/instagram_events_job.rb
  (the standalone Channel::Instagram path; the legacy FB-page-IG
   branch lives in a follow-up sub-phase).

Walks Meta's IG webhook payload + creates Contact + ContactInbox +
Conversation + Message rows. The shape matches Messenger's
``entry[].messaging[]`` array but ``entry.id`` identifies the IG
Business account (not a Facebook page) and contacts are keyed by
Instagram Scoped User Id (IGSID).

Payload shape:

    {
      "object": "instagram",
      "entry": [
        {
          "id": "<INSTAGRAM_ID>",
          "messaging": [
            {
              "sender":    {"id": "<IGSID>"},
              "recipient": {"id": "<INSTAGRAM_ID>"},
              "timestamp": <ms>,
              "message":   {"mid": "<MID>", "text": "..."}
            }
          ]
        }
      ]
    }

5e.3 scope:
  * Text messages.
  * ``message.is_echo`` — agent replied via the IG mobile app.
    Stamped as outgoing with ``sender_id=None``, mirroring 5d.3.
  * Idempotent on Meta's ``mid`` via ``messages.source_id``.
  * Read events (``messaging.read.mid``) update the Message status.

Deferred:
  * Story replies / story mentions (``messaging.story_reply``).
  * Reactions.
  * Postbacks / quick_replies — same as Messenger.
  * Watermark-based bulk read (``messaging.read.watermark`` to mark
    every message before T as read).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_STATUS_READ,
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
    CHANNEL_TYPE_INSTAGRAM,
    Inbox,
    InstagramChannel,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel resolution
# ---------------------------------------------------------------------------
async def _resolve_channel(
    session: AsyncSession, *, instagram_id: str
) -> tuple[InstagramChannel, Inbox] | None:
    """Look up the InstagramChannel + Inbox by IG id."""
    channel = (
        await session.exec(
            select(InstagramChannel).where(
                InstagramChannel.instagram_id == instagram_id
            )
        )
    ).first()
    if channel is None:
        return None
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_INSTAGRAM,
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
    igsid: str,
) -> Contact:
    """Find a contact by Instagram Scoped User Id via its
    ContactInbox; create one if the IGSID is new."""
    existing = (
        await session.exec(
            select(Contact)
            .join(ContactInbox, ContactInbox.contact_id == Contact.id)
            .where(
                Contact.account_id == account_id,
                ContactInbox.source_id == igsid,
            )
        )
    ).first()
    if existing is not None:
        return existing

    placeholder = (
        f"instagram-{igsid[-6:]}"
        if len(igsid) >= 6
        else f"instagram-{igsid}"
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
    mint a new one. IG threads are durable per-IGSID, same as
    Messenger threads per-PSID."""
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
# Read events
# ---------------------------------------------------------------------------
async def _process_read_event(
    session: AsyncSession,
    *,
    account_id: int,
    event: dict[str, Any],
) -> list[Message]:
    """Update the outbound message whose mid is in the read event.

    IG's ``read`` field carries ``mid`` (singular) plus a ``watermark``
    timestamp. We honour the explicit mid; watermark-based bulk-read
    (mark every message before T as read) lands later.
    """
    read = event.get("read")
    if not isinstance(read, dict):
        return []
    mid = read.get("mid")
    if not mid:
        return []
    msg = (
        await session.exec(
            select(Message).where(
                Message.account_id == account_id,
                Message.source_id == str(mid),
            )
        )
    ).first()
    if msg is None:
        return []
    msg.status = MESSAGE_STATUS_READ
    session.add(msg)
    await session.flush()
    return [msg]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def process_instagram_webhook(
    session: AsyncSession,
    *,
    payload: dict[str, Any],
) -> list[Message]:
    """Convert one IG webhook payload to Message rows.

    Returns the list of messages created or updated. Empty list is
    fine (status-only update, unknown IG account, duplicate mid,
    etc).
    """
    if str((payload or {}).get("object", "")).lower() != "instagram":
        return []
    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        return []

    out: list[Message] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ig_id = str(entry.get("id") or "")
        if not ig_id:
            continue
        resolved = await _resolve_channel(session, instagram_id=ig_id)
        if resolved is None:
            continue
        channel, inbox = resolved

        for event in entry.get("messaging") or []:
            if not isinstance(event, dict):
                continue
            if "read" in event:
                out.extend(
                    await _process_read_event(
                        session,
                        account_id=channel.account_id,
                        event=event,
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
    channel: InstagramChannel,
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

    # Echoes: IGSID lives in ``recipient``. Inbound: in ``sender``.
    igsid = (
        recipient_block.get("id")
        if is_echo
        else sender_block.get("id")
    )
    igsid = str(igsid or "")
    if not igsid:
        return None

    already = (
        await session.exec(
            select(Message.id).where(
                Message.account_id == channel.account_id,
                Message.source_id == str(mid),
            )
        )
    ).first()
    if already is not None:
        log.info("instagram.inbound.skip reason=duplicate mid=%s", mid)
        return None

    contact = await _find_or_create_contact(
        session, account_id=channel.account_id, igsid=igsid
    )
    contact_inbox = await ContactInboxBuilder(
        session=session,
        contact=contact,
        inbox=inbox,
        source_id=igsid,
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
    except Exception:  # noqa: BLE001
        log.exception("instagram.inbound.create_message_failed mid=%s", mid)
        return None
    return msg


__all__ = ["process_instagram_webhook"]
