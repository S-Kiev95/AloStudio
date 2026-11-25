"""WhatsApp coexistence: a number that stays on the WhatsApp Business app.

When a business connects through Embedded Signup with its existing
WhatsApp Business app number (it scans Meta's QR with the phone), the
number moves to the Cloud API and keeps working on the phone, with its
chats. Meta then sends, besides the usual ``messages``:

* ``history``: the chats of the last 6 months (if the business agreed to
  share them), in chunks. Stored quietly: no bot, automation or
  notification runs on messages that are months old.
* ``smb_app_state_sync``: the phone's WhatsApp contacts.
* ``smb_message_echoes``: what the business answers from the phone, shown
  in the Bandeja like an agent's reply (handled in ``incoming_cloud``).
* ``account_update``: the business disconnected the number from the app
  (``PARTNER_REMOVED``) or Meta did it after the phone was offline.

Docs: developers.facebook.com/docs/whatsapp/embedded-signup/custom-flows/
onboarding-business-app-users
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONTENT_TYPE_TEXT,
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_STATUS_DELIVERED,
    MESSAGE_STATUS_READ,
    MESSAGE_STATUS_SENT,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    SENDER_TYPE_CONTACT,
    Conversation,
    Message,
)
from app.domains.inboxes.models import Inbox, WhatsappChannel

log = logging.getLogger(__name__)

# The business turned history sharing off in the app.
_HISTORY_DECLINED = 2593109
# account_update events that end or restore coexistence.
_DISCONNECTED = frozenset({"PARTNER_REMOVED", "ACCOUNT_OFFBOARDED"})
_RECONNECTED = "ACCOUNT_RECONNECTED"

_HISTORY_STATUS: dict[str, int] = {
    "sent": MESSAGE_STATUS_SENT,
    "delivered": MESSAGE_STATUS_DELIVERED,
    "read": MESSAGE_STATUS_READ,
    "played": MESSAGE_STATUS_READ,
}


def is_coexistence(channel: WhatsappChannel) -> bool:
    return bool((channel.provider_config or {}).get("coexistence"))


def _plus(number: str) -> str:
    return number if number.startswith("+") else f"+{number}"


def _digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _when(raw: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(raw), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _note_sync(channel: WhatsappChannel, **fields: Any) -> None:
    """Keep the sync's progress on the channel, for the inbox settings."""
    config = dict(channel.provider_config or {})
    sync = dict(config.get("coexistence_sync") or {})
    sync.update(fields)
    config["coexistence_sync"] = sync
    channel.provider_config = config


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------
async def _quiet_conversation(
    session: AsyncSession, *, inbox: Inbox, contact_id: int, contact_inbox_id: int, at: datetime
) -> Conversation:
    """The contact's latest conversation, or a resolved one for old chats.
    Created without events: an old chat must not wake bots or assign agents."""
    latest = (
        await session.exec(
            select(Conversation)
            .where(Conversation.contact_inbox_id == contact_inbox_id)
            .order_by(col(Conversation.id).desc())
            .limit(1)
        )
    ).first()
    if latest is not None:
        return latest
    conversation = Conversation(
        account_id=inbox.account_id,
        inbox_id=inbox.id,
        contact_id=contact_id,
        contact_inbox_id=contact_inbox_id,
        status=CONVERSATION_STATUS_RESOLVED,
        last_activity_at=at,
        waiting_since=None,
        created_at=at,
    )
    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)
    return conversation


async def _import_message(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    customer: str,
    msg: dict[str, Any],
    outgoing: bool,
) -> Message | None:
    from app.domains.conversations.service import _apply_attachments
    from app.domains.whatsapp.incoming_cloud import (
        _build_media_attachments,
        _echo_text,
        _find_or_create_contact,
        _message_text,
    )

    wamid = msg.get("id")
    msg_type = str(msg.get("type") or "")
    # The content of a media message comes later, in its own webhook.
    if not wamid or not msg_type or msg_type == "media_placeholder":
        return None
    already = (
        await session.exec(
            select(Message.id).where(
                Message.account_id == channel.account_id, Message.source_id == str(wamid)
            )
        )
    ).first()
    if already is not None:
        return None
    at = _when(msg.get("timestamp")) or datetime.now(UTC)
    phone = _plus(customer)
    contact = await _find_or_create_contact(
        session, account_id=channel.account_id, phone_number=phone, name=None
    )
    contact_inbox = await ContactInboxBuilder(
        session=session, contact=contact, inbox=inbox, source_id=phone
    ).perform()
    assert contact.id is not None and contact_inbox.id is not None
    conversation = await _quiet_conversation(
        session,
        inbox=inbox,
        contact_id=contact.id,
        contact_inbox_id=contact_inbox.id,
        at=at,
    )
    attachments, caption = await _build_media_attachments(
        channel=channel, msg=msg, msg_type=msg_type
    )
    text = _message_text(msg) or caption
    if not text and not attachments:
        text = _echo_text({"type": msg_type, msg_type: msg.get(msg_type)})
    history_status = (msg.get("history_context") or {}).get("status")
    message = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conversation.id,
        sender_type=None if outgoing else SENDER_TYPE_CONTACT,
        sender_id=None if outgoing else contact.id,
        message_type=MESSAGE_TYPE_OUTGOING if outgoing else MESSAGE_TYPE_INCOMING,
        content_type=CONTENT_TYPE_TEXT,
        content=text or None,
        processed_message_content=text or None,
        content_attributes={"external_echo": True, "imported_history": True},
        status=_HISTORY_STATUS.get(str(history_status), MESSAGE_STATUS_SENT),
        source_id=str(wamid),
        created_at=at,
        updated_at=at,
    )
    try:
        async with session.begin_nested():
            session.add(message)
            await session.flush()
            if attachments:
                await _apply_attachments(session, message=message, specs=attachments)
                await session.flush()
    except IntegrityError:
        log.info("whatsapp.coexistence.skip reason=duplicate_race wamid=%s", wamid)
        return None
    return message


async def import_history(
    session: AsyncSession, *, channel: WhatsappChannel, inbox: Inbox, value: dict[str, Any]
) -> list[Message]:
    """One ``history`` webhook: chunks of threads, or a media message's
    content (``messages``), or the business declining to share."""
    business = _digits((value.get("metadata") or {}).get("display_phone_number"))
    out: list[Message] = []
    for chunk in value.get("history") or []:
        if not isinstance(chunk, dict):
            continue
        errors = chunk.get("errors") or []
        if any(isinstance(e, dict) and e.get("code") == _HISTORY_DECLINED for e in errors):
            _note_sync(channel, history="declined")
            log.info("whatsapp.coexistence.history_declined channel_id=%s", channel.id)
            continue
        meta = chunk.get("metadata") or {}
        for thread in chunk.get("threads") or []:
            if not isinstance(thread, dict):
                continue
            context = thread.get("context") or {}
            customer = _digits(thread.get("id") or context.get("wa_id"))
            if not customer:
                continue  # Only a business-scoped id: no number to file it under.
            for msg in thread.get("messages") or []:
                if not isinstance(msg, dict):
                    continue
                outgoing = bool(msg.get("to")) or _digits(msg.get("from")) == business
                stored = await _import_message(
                    session,
                    channel=channel,
                    inbox=inbox,
                    customer=customer,
                    msg=msg,
                    outgoing=outgoing,
                )
                if stored is not None:
                    out.append(stored)
        if isinstance(meta, dict) and meta.get("progress") is not None:
            _note_sync(channel, history="importing", progress=meta.get("progress"))
            if meta.get("progress") == 100:
                _note_sync(channel, history="done")
    # A media message from the history, with its content this time.
    for msg in value.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        sender = _digits(msg.get("from"))
        outgoing = bool(msg.get("to")) or sender == business
        customer = _digits(msg.get("to")) if outgoing else sender
        if not customer:
            continue
        stored = await _import_message(
            session, channel=channel, inbox=inbox, customer=customer, msg=msg, outgoing=outgoing
        )
        if stored is not None:
            out.append(stored)
    session.add(channel)
    await session.flush()
    return out


# ---------------------------------------------------------------------------
# smb_app_state_sync
# ---------------------------------------------------------------------------
async def sync_contacts(
    session: AsyncSession, *, channel: WhatsappChannel, value: dict[str, Any]
) -> int:
    """The phone's WhatsApp contacts become contacts here, named as on the
    phone. A contact removed on the phone stays: it may have chats here."""
    from app.domains.whatsapp.incoming_cloud import _find_or_create_contact

    count = 0
    for item in value.get("state_sync") or []:
        if not isinstance(item, dict) or item.get("type") != "contact":
            continue
        if item.get("action") != "add":
            continue
        contact = item.get("contact") or {}
        number = _digits(contact.get("phone_number"))
        if not number:
            continue
        name = contact.get("full_name") or contact.get("first_name")
        await _find_or_create_contact(
            session,
            account_id=channel.account_id,
            phone_number=_plus(number),
            name=str(name) if name else None,
        )
        count += 1
    if count:
        _note_sync(channel, contacts="done")
        session.add(channel)
        await session.flush()
    return count


# ---------------------------------------------------------------------------
# account_update
# ---------------------------------------------------------------------------
def _account_updates(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """``(waba_id, value)`` for every ``account_update`` change. The WABA is
    in ``waba_info``, or the entry id for the offboarded/reconnected events."""
    out: list[tuple[str, dict[str, Any]]] = []
    for entry in (payload or {}).get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict) or change.get("field") != "account_update":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            waba = (value.get("waba_info") or {}).get("waba_id") or entry.get("id")
            if waba:
                out.append((str(waba), value))
    return out


async def process_account_updates(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Mark coexistence numbers the business (or Meta) disconnected, and
    clear the mark when they reconnect. They stop receiving until then."""
    table = WhatsappChannel.__table__  # type: ignore[attr-defined]
    for waba_id, value in _account_updates(payload):
        event = str(value.get("event") or "")
        if event not in _DISCONNECTED and event != _RECONNECTED:
            continue
        channels = (
            await session.exec(
                select(WhatsappChannel).where(
                    table.c.provider_config["business_account_id"].astext == waba_id
                )
            )
        ).all()
        for channel in channels:
            if not is_coexistence(channel):
                continue
            config = dict(channel.provider_config or {})
            if event == _RECONNECTED:
                config.pop("coexistence_disconnected", None)
            else:
                info = value.get("disconnection_info") or {}
                config["coexistence_disconnected"] = {
                    "event": event,
                    "reason": info.get("reason"),
                    "initiated_by": info.get("initiated_by"),
                    "at": datetime.now(UTC).isoformat(),
                }
            channel.provider_config = config
            session.add(channel)
            log.warning(
                "whatsapp.coexistence.account_update channel_id=%s event=%s reason=%s",
                channel.id,
                event,
                (value.get("disconnection_info") or {}).get("reason"),
            )
    await session.flush()


__all__ = [
    "import_history",
    "is_coexistence",
    "process_account_updates",
    "sync_contacts",
]
