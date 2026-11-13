"""Contact origin: how each person first reached the business (F11).

The first conversation stamps it: the channel it arrived on, upgraded to the
ad, post or short link when Meta's referral says so. People can also set it
by hand for what the system cannot see (a recommendation, a fair, a walk-in).
First touch wins: a later conversation never rewrites an origin.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.inboxes.models import (
    CHANNEL_TYPE_API,
    CHANNEL_TYPE_EMAIL,
    CHANNEL_TYPE_FACEBOOK,
    CHANNEL_TYPE_INSTAGRAM,
    CHANNEL_TYPE_SMS,
    CHANNEL_TYPE_TELEGRAM,
    CHANNEL_TYPE_TWILIO_SMS,
    CHANNEL_TYPE_WEB_WIDGET,
    CHANNEL_TYPE_WHATSAPP,
)

# Set automatically.
SOURCE_CHANNEL = "channel"
AUTO_SOURCES = ("channel", "ad", "post", "shortlink")
# Set by hand.
MANUAL_SOURCES = ("referral", "event", "walk_in", "phone", "website", "other")
SOURCES = AUTO_SOURCES + MANUAL_SOURCES

CHANNEL_CODES: dict[str, str] = {
    CHANNEL_TYPE_WHATSAPP: "whatsapp",
    CHANNEL_TYPE_INSTAGRAM: "instagram",
    CHANNEL_TYPE_FACEBOOK: "facebook",
    CHANNEL_TYPE_WEB_WIDGET: "web",
    CHANNEL_TYPE_EMAIL: "email",
    CHANNEL_TYPE_TELEGRAM: "telegram",
    CHANNEL_TYPE_SMS: "sms",
    CHANNEL_TYPE_TWILIO_SMS: "sms",
    CHANNEL_TYPE_API: "api",
}
CHANNELS = tuple(sorted(set(CHANNEL_CODES.values())))


def channel_code(channel_type: str | None) -> str | None:
    return CHANNEL_CODES.get(channel_type or "")


def ad_source(value: str | None) -> str:
    """Meta's referral source as an origin code (unknown kinds count as ads)."""
    return value if value in ("ad", "post", "shortlink") else "ad"


async def _contact(session: AsyncSession, contact_id: int) -> Contact | None:
    return (await session.exec(select(Contact).where(Contact.id == contact_id))).first()


async def stamp_from_conversation(
    session: AsyncSession, conversation: Conversation, channel_type: str | None
) -> bool:
    """Give the contact its origin from their first conversation, if unset."""
    contact = await _contact(session, conversation.contact_id)
    if contact is None or contact.source:
        return False
    contact.source = SOURCE_CHANNEL
    contact.source_channel = channel_code(channel_type)
    contact.source_conversation_id = conversation.id
    contact.source_at = datetime.now(UTC)
    if conversation.ad_id or conversation.ad_source:
        _apply_ad(contact, conversation)
    session.add(contact)
    return True


async def stamp_from_referral(session: AsyncSession, conversation: Conversation) -> bool:
    """Upgrade an origin to the ad once the conversation that set it learns
    which ad brought the person. Origins set by hand or by an older
    conversation stay as they are."""
    contact = await _contact(session, conversation.contact_id)
    if contact is None:
        return False
    if contact.source and not (
        contact.source == SOURCE_CHANNEL
        and contact.source_conversation_id == conversation.id
    ):
        return False
    if not contact.source:
        contact.source_conversation_id = conversation.id
        contact.source_at = datetime.now(UTC)
    _apply_ad(contact, conversation)
    session.add(contact)
    return True


def _apply_ad(contact: Contact, conversation: Conversation) -> None:
    contact.source = ad_source(conversation.ad_source)
    contact.source_detail = conversation.ad_headline
    contact.source_ad_id = conversation.ad_id


def set_origin(
    contact: Contact,
    *,
    source: str | None,
    channel: str | None,
    detail: str | None,
) -> None:
    """Set (or clear, with ``source=None``) a contact's origin by hand."""
    if source is None:
        contact.source = None
        contact.source_channel = None
        contact.source_detail = None
        contact.source_ad_id = None
        contact.source_conversation_id = None
        contact.source_at = None
        return
    if source not in SOURCES:
        raise ValueError("unknown source")
    if channel is not None and channel not in CHANNELS:
        raise ValueError("unknown channel")
    if source != contact.source:
        contact.source_ad_id = None
        contact.source_conversation_id = None
    contact.source = source
    contact.source_channel = channel
    contact.source_detail = (detail or "").strip() or None
    contact.source_at = contact.source_at or datetime.now(UTC)


def present_origin(contact: Contact) -> dict[str, object] | None:
    if not contact.source:
        return None
    return {
        "source": contact.source,
        "channel": contact.source_channel,
        "detail": contact.source_detail,
        "ad_id": contact.source_ad_id,
        "conversation_id": contact.source_conversation_id,
        "at": int(contact.source_at.timestamp()) if contact.source_at else None,
    }
