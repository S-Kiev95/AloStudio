"""WhatsApp Cloud webhook payload processor.

Ported from:
  reference/chatwoot/app/services/whatsapp/incoming_message_base_service.rb
  reference/chatwoot/app/services/whatsapp/incoming_message_whatsapp_cloud_service.rb
  reference/chatwoot/app/services/whatsapp/incoming_message_service_helpers.rb

Given Meta's webhook payload (Cloud API v17+ shape) and the matching
:class:`WhatsappChannel`, this module:

  1. Walks ``entry[0].changes[0].value.messages[]`` (the inbound
     messages bundle) + ``contacts[]`` (sender profile data).
  2. Resolves each ``from`` (E.164 phone) to a :class:`Contact` —
     creating one when the number is new on this account, attaching
     the WhatsApp profile name when present.
  3. Resolves a :class:`ContactInbox` keyed by ``source_id == phone``
     (the dedup pivot Chatwoot's email/widget channels also follow).
  4. Creates / re-uses a :class:`Conversation` per ContactInbox —
     inbox-locked semantics from
     :func:`app.domains.conversations.service.create_conversation`.
  5. Inserts an incoming :class:`Message` with the parsed text body.
     Stamps ``source_id`` with Meta's WAMID so re-delivery (Meta
     occasionally fires a webhook twice) is idempotent.

Also handles ``statuses`` events (delivery / read / failed
confirmations) — looks up the existing message by WAMID and updates
its ``status`` enum + stashes any error code/title in
``content_attributes``.

5c.3 scope:
  * Text messages.
  * ``button`` / ``interactive`` reply text (Meta's rich-button replies).
  * Status updates (sent / delivered / read / failed).
  * Idempotent re-delivery via WAMID lookup.

Deferred to 5c.6 / later:
  * Media (image / video / audio / document / sticker) — needs the
    media-download client + Phase 10 attachment storage.
  * Reactions / ephemeral / unsupported message types — Chatwoot
    explicitly drops these. We mirror.
  * Contact-card messages.
  * Location messages.
  * Outgoing echoes (``message_echoes``) — niche, lands with the
    embedded-signup flow in 5c.6.
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
    MESSAGE_STATUS_FAILED,
    MESSAGE_STATUS_READ,
    MESSAGE_STATUS_SENT,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams as _MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.inboxes.models import Inbox, WhatsappChannel

log = logging.getLogger(__name__)


# Message types we silently drop — Chatwoot's
# ``unprocessable_message_type?`` allow-list inverted.
_UNPROCESSABLE_TYPES = frozenset(
    {"reaction", "ephemeral", "unsupported", "request_welcome"}
)

# Meta status -> our integer enum.
_STATUS_MAP: dict[str, int] = {
    "sent": MESSAGE_STATUS_SENT,
    "delivered": MESSAGE_STATUS_DELIVERED,
    "read": MESSAGE_STATUS_READ,
    "failed": MESSAGE_STATUS_FAILED,
}


# ---------------------------------------------------------------------------
# Payload accessors
# ---------------------------------------------------------------------------
def _value(payload: dict[str, Any]) -> dict[str, Any]:
    """Pluck ``entry[0].changes[0].value`` from a Cloud webhook payload.

    Returns an empty dict when any nested key is missing — Meta's
    payload shape is well-defined but we want to fail soft on a
    malformed body rather than raise into the webhook handler.
    """
    entry = (payload or {}).get("entry") or []
    if not entry or not isinstance(entry[0], dict):
        return {}
    changes = entry[0].get("changes") or []
    if not changes or not isinstance(changes[0], dict):
        return {}
    value = changes[0].get("value") or {}
    return value if isinstance(value, dict) else {}


def _message_text(message: dict[str, Any]) -> str:
    """Mirror ``message_content`` — text / button / interactive replies."""
    text = message.get("text")
    if isinstance(text, dict) and text.get("body"):
        return str(text["body"])
    button = message.get("button")
    if isinstance(button, dict) and button.get("text"):
        return str(button["text"])
    interactive = message.get("interactive")
    if isinstance(interactive, dict):
        for key in ("button_reply", "list_reply"):
            sub = interactive.get(key)
            if isinstance(sub, dict) and sub.get("title"):
                return str(sub["title"])
    name = message.get("name")
    if isinstance(name, dict) and name.get("formatted_name"):
        return str(name["formatted_name"])
    return ""


def _contact_name_for(
    sender_phone: str, contacts_block: list[dict[str, Any]]
) -> str | None:
    """Find the WhatsApp profile name in the ``contacts`` block.

    Cloud payloads ship a parallel ``contacts`` array indexed by
    ``wa_id`` (== sender phone). We pluck the first matching entry's
    ``profile.name`` to use as the contact's display name.
    """
    if not contacts_block:
        return None
    for c in contacts_block:
        if not isinstance(c, dict):
            continue
        if c.get("wa_id") == sender_phone:
            profile = c.get("profile")
            if isinstance(profile, dict):
                name = profile.get("name")
                if name:
                    return str(name)
    return None


# ---------------------------------------------------------------------------
# Contact / conversation resolution
# ---------------------------------------------------------------------------
async def _find_or_create_contact(
    session: AsyncSession,
    *,
    account_id: int,
    phone_number: str,
    name: str | None,
) -> Contact:
    """Resolve a contact by phone — create one if the number is new."""
    existing = (
        await session.exec(
            select(Contact).where(
                Contact.account_id == account_id,
                Contact.phone_number == phone_number,
            )
        )
    ).first()
    if existing is not None:
        # If we have a fresher profile name and the contact's name was
        # the placeholder phone, upgrade it. Mirrors Chatwoot's
        # ``set_contact_from_message`` behaviour where a new profile
        # name overrides the prior anonymous label.
        if name and (not existing.name or existing.name == phone_number):
            existing.name = name
            session.add(existing)
            await session.flush()
        return existing

    contact = Contact(
        account_id=account_id,
        phone_number=phone_number,
        name=name or phone_number,
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
    """Re-use the most recent open conversation on this ContactInbox,
    else mint a fresh one.

    Chatwoot's ``set_conversation`` does the same: it picks the
    latest conversation whose ``status`` isn't ``resolved``, and
    only creates a new one when none exists.
    """
    latest = (
        await session.exec(
            select(Conversation)
            .where(Conversation.contact_inbox_id == contact_inbox.id)
            .order_by(Conversation.id.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
    ).first()
    # Reopen even resolved conversations on inbound — matches the
    # Phase 4a post-create cascade for incoming messages, which the
    # MessageBuilder already runs for us via ``create_message``.
    if latest is not None:
        return latest
    return await create_conversation(
        session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(),
    )


# ---------------------------------------------------------------------------
# Status processor
# ---------------------------------------------------------------------------
async def _process_status(
    session: AsyncSession, *, account_id: int, status: dict[str, Any]
) -> Message | None:
    """Update a previously-sent message's status from Meta's status webhook.

    Mirrors ``update_message_with_status``. Meta sends the WAMID in
    ``status.id``; we look it up via ``Message.source_id``.
    """
    wamid = status.get("id")
    if not wamid:
        return None
    msg = (
        await session.exec(
            select(Message).where(
                Message.account_id == account_id,
                Message.source_id == wamid,
            )
        )
    ).first()
    if msg is None:
        return None

    new_status = _STATUS_MAP.get(str(status.get("status") or ""))
    if new_status is None:
        return None
    msg.status = new_status
    if new_status == MESSAGE_STATUS_FAILED:
        errors = status.get("errors") or []
        if errors and isinstance(errors[0], dict):
            err = errors[0]
            ca = dict(msg.content_attributes or {})
            ca["external_error"] = (
                f"{err.get('code')}: {err.get('title')}"
            )
            msg.content_attributes = ca
    session.add(msg)
    await session.flush()
    return msg


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def process_cloud_webhook(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    payload: dict[str, Any],
) -> list[Message]:
    """Convert one Meta Cloud webhook payload to Message rows.

    Returns the list of messages that were created or updated. Empty
    list is fine (statuses-only update, unprocessable message type,
    duplicate WAMID, etc).
    """
    value = _value(payload)
    if not value:
        return []

    out: list[Message] = []

    # Status events get processed first — they reference messages we
    # already have, no contact / conversation resolution needed.
    statuses = value.get("statuses") or []
    if isinstance(statuses, list):
        for st in statuses:
            if not isinstance(st, dict):
                continue
            updated = await _process_status(
                session, account_id=channel.account_id, status=st
            )
            if updated is not None:
                out.append(updated)

    messages = value.get("messages") or []
    if not isinstance(messages, list) or not messages:
        return out

    contacts_block = value.get("contacts") or []

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        msg_type = msg.get("type")
        if msg_type in _UNPROCESSABLE_TYPES:
            continue

        wamid = msg.get("id")
        if not wamid:
            continue

        # Idempotent: skip if we've already ingested this WAMID.
        already = (
            await session.exec(
                select(Message.id).where(
                    Message.account_id == channel.account_id,
                    Message.source_id == wamid,
                )
            )
        ).first()
        if already is not None:
            log.info(
                "whatsapp.inbound.skip reason=duplicate wamid=%s", wamid
            )
            continue

        sender_phone = str(msg.get("from") or "")
        if not sender_phone:
            continue

        # Chatwoot stores the phone with a leading ``+`` even though
        # WhatsApp transmits the bare ``wa_id``. We mirror that.
        normalized_phone = (
            sender_phone if sender_phone.startswith("+")
            else f"+{sender_phone}"
        )
        profile_name = _contact_name_for(sender_phone, contacts_block)

        contact = await _find_or_create_contact(
            session,
            account_id=channel.account_id,
            phone_number=normalized_phone,
            name=profile_name,
        )
        contact_inbox = await ContactInboxBuilder(
            session=session,
            contact=contact,
            inbox=inbox,
            source_id=normalized_phone,
        ).perform()
        conversation = await _find_or_create_conversation(
            session, contact_inbox=contact_inbox
        )

        body = _message_text(msg)
        try:
            inserted = await create_message(
                session,
                conversation=conversation,
                params=_MessageBuilderParams(
                    content=body,
                    message_type="incoming",
                    source_id=str(wamid),
                ),
                user_id=None,
            )
        except Exception:  # noqa: BLE001
            log.exception(
                "whatsapp.inbound.create_message_failed wamid=%s", wamid
            )
            continue
        out.append(inserted)

    return out


__all__ = ["process_cloud_webhook"]
