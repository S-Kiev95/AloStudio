"""Inbound email processor.

Ported from:
  reference/chatwoot/app/services/imap/imap_mailbox.rb
  reference/chatwoot/app/services/imap/base_fetch_email_service.rb
    (the message-to-row half — IMAP transport lives in
     :mod:`app.domains.email.imap_fetch`).

Given a parsed :class:`email.message.EmailMessage` and a
:class:`Channel::Email`, this module:

  1. Resolves the ``From:`` address to a :class:`Contact` (creating
     one when no match exists in the account).
  2. Resolves / creates the :class:`ContactInbox` keyed by
     ``source_id == contact.email`` (matches Chatwoot's email-channel
     ContactInbox pattern).
  3. Runs the threading parser
     (:func:`app.domains.email.threading.find_conversation_by_thread`)
     over ``In-Reply-To`` + ``References`` to locate an existing
     conversation, falling back to a new one.
  4. Inserts the incoming :class:`Message` carrying the parsed body,
     stamping ``source_id`` = bare ``Message-ID`` so the threading
     lookup hits it on the next inbound. Also stashes the original
     message-id under ``content_attributes.email.message_id`` so the
     outbound mailer's ``In-Reply-To`` builder finds it.

Pure async — the function takes an :class:`AsyncSession` and writes
through the same path :func:`create_message` uses for the agent-side
flow, so post-create hooks (last_activity_at bump, MESSAGE_CREATED
broadcast) fire identically.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
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
from app.domains.email.threading import (
    ThreadingHeaders,
    extract_message_ids,
    find_conversation_by_thread,
)
from app.domains.inboxes.models import EmailChannel, Inbox

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------
def _strip_brackets(value: str | None) -> str | None:
    """``<id@host>`` -> ``id@host``. Returns ``None`` for blank input."""
    if not value:
        return None
    v = value.strip()
    if v.startswith("<") and v.endswith(">"):
        v = v[1:-1]
    return v or None


def _from_address(mail: EmailMessage) -> tuple[str | None, str | None]:
    """Return ``(display_name, email)`` from the ``From:`` header.

    Handles RFC-2822 ``"Alice" <alice@example.com>``, the bare
    ``alice@example.com``, and the malformed-but-common
    ``alice@example.com (Alice)``. Returns ``(None, None)`` when the
    header is absent / unparseable.
    """
    raw = mail.get("From")
    if not raw:
        return None, None
    name, addr = parseaddr(raw)
    if not addr or "@" not in addr:
        return None, None
    return (name.strip() or None), addr.lower()



def _header_addresses(mail: EmailMessage, header: str) -> list[str]:
    """Every address on one header, as plain strings.

    A list, not the raw header: "To" routinely carries several, and a UI
    that has to re-parse RFC-2822 to show them will get it wrong on the
    first name containing a comma.
    """
    raw = mail.get(header)
    if not raw:
        return []
    return [
        addr
        for _name, addr in getaddresses([str(raw)])
        if addr and "@" in addr
    ]


def _extract_body(mail: EmailMessage) -> str:
    """Pull the plain-text body.

    Multipart mails get their first ``text/plain`` part; HTML-only
    mails fall through to a stripped HTML body. Empty body is
    represented as ``""`` so the caller can still create a Message
    row with no content (matches Rails' ``message.content = ''``).
    """
    if mail.is_multipart():
        for part in mail.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                payload = part.get_content()
                return payload.strip() if isinstance(payload, str) else ""
        # No text/plain — fall back to first text/html stripped.
        for part in mail.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_content()
                if isinstance(payload, str):
                    return _strip_html_tags(payload).strip()
        return ""
    payload = mail.get_content()
    if isinstance(payload, str):
        if mail.get_content_type() == "text/html":
            return _strip_html_tags(payload).strip()
        return payload.strip()
    return ""


def _strip_html_tags(html: str) -> str:
    """Best-effort HTML -> plain text. We just drop tags + collapse
    whitespace; full HTML rendering parity (line breaks for ``<br>``,
    blockquotes, etc) lands with the same hardening pass that ports
    Chatwoot's ``HtmlParser::Sanitizer``.
    """
    import re

    no_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", no_tags).strip()


# ---------------------------------------------------------------------------
# Contact resolution
# ---------------------------------------------------------------------------
async def _find_or_create_contact(
    session: AsyncSession,
    *,
    account_id: int,
    email: str,
    name: str | None,
) -> Contact:
    """Match an inbound email to a contact.

    Lookup order mirrors ``ContactInboxWithContactBuilder#find_contact``:
    by email first, then create. Identifier lookups via custom_attribute
    or phone_number aren't relevant for inbound mail.
    """
    existing = (
        await session.exec(
            select(Contact).where(
                Contact.account_id == account_id,
                Contact.email == email,
            )
        )
    ).first()
    if existing is not None:
        return existing

    contact = Contact(
        account_id=account_id,
        email=email,
        name=name or email.split("@", 1)[0],
    )
    session.add(contact)
    await session.flush()
    await session.refresh(contact)
    return contact


async def _find_or_create_contact_inbox(
    session: AsyncSession,
    *,
    contact: Contact,
    inbox: Inbox,
) -> ContactInbox:
    """Mirror Chatwoot's email-channel ContactInbox flow.

    The Email branch of :class:`ContactInboxBuilder` already keys on
    ``contact.email`` for the source_id, so we delegate. The builder's
    find-existing branch fires the fast path when the contact has
    written before.
    """
    return await ContactInboxBuilder(
        session=session, contact=contact, inbox=inbox
    ).perform()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def process_inbound_email(
    session: AsyncSession,
    *,
    channel: EmailChannel,
    inbox: Inbox,
    mail: EmailMessage,
) -> Message | None:
    """Convert one inbound mail to a :class:`Message` row.

    Returns the inserted message, or ``None`` when the mail should be
    skipped (no parseable From, duplicate Message-ID we've already
    ingested, etc).
    """
    sender_name, sender_email = _from_address(mail)
    if not sender_email:
        log.info("email.inbound.skip reason=no_from_address")
        return None

    # Idempotency: if we've already ingested this Message-ID skip it.
    # Chatwoot relies on the same check via
    # ``Message.find_by(source_id: ...)``.
    raw_mid = mail.get("Message-ID")
    bare_mid = _strip_brackets(raw_mid)
    if bare_mid:
        already = (
            await session.exec(
                select(Message.id).where(
                    Message.account_id == channel.account_id,
                    Message.source_id == bare_mid,
                )
            )
        ).first()
        if already is not None:
            log.info(
                "email.inbound.skip reason=duplicate message_id=%s", bare_mid
            )
            return None

    # 1. Contact + ContactInbox.
    contact = await _find_or_create_contact(
        session,
        account_id=channel.account_id,
        email=sender_email,
        name=sender_name,
    )
    contact_inbox = await _find_or_create_contact_inbox(
        session, contact=contact, inbox=inbox
    )

    # 2. Threading lookup.
    headers = ThreadingHeaders(
        in_reply_to=mail.get("In-Reply-To"),
        references=mail.get("References"),
        message_id=raw_mid,
    )
    conversation = await find_conversation_by_thread(
        session, account_id=channel.account_id, headers=headers
    )

    # 3. New conversation if no thread match.
    if conversation is None:
        conversation = await create_conversation(
            session,
            contact_inbox=contact_inbox,
            params=ConversationBuilderParams(
                additional_attributes={
                    "mail_subject": (mail.get("Subject") or "").strip(),
                },
            ),
        )

    # 4. Create the incoming message + stash threading metadata.
    body = _extract_body(mail)
    # The headers a reader needs to see this as an email rather than a
    # chat line: who it was addressed to, who else got it, and what it
    # was about. Only the message-id was kept before, which is enough to
    # thread and not enough to display.
    content_attrs: dict[str, Any] = {
        "email": {
            "subject": (mail.get("Subject") or "").strip() or None,
            "from": sender_email,
            "from_name": sender_name or None,
            "to": _header_addresses(mail, "To"),
            "cc": _header_addresses(mail, "Cc"),
            "date": (mail.get("Date") or "").strip() or None,
        }
    }
    if bare_mid:
        content_attrs["email"]["message_id"] = bare_mid
        # Persist the chain too — useful for audit + future outbounds
        # that want to extend the References header.
        ref_ids = extract_message_ids(mail.get("References"))
        if ref_ids:
            content_attrs["email"]["references"] = ref_ids
        if mail.get("In-Reply-To"):
            content_attrs["email"]["in_reply_to"] = _strip_brackets(
                mail.get("In-Reply-To")
            )

    message = await create_message(
        session,
        conversation=conversation,
        params=_MessageBuilderParams(
            content=body,
            message_type="incoming",
            content_attributes=content_attrs,
            source_id=bare_mid,
        ),
        user_id=None,
    )
    log.info(
        "email.inbound.created channel_id=%s conversation_id=%s message_id=%s",
        channel.id,
        conversation.id,
        message.id,
    )
    return message


__all__ = ["process_inbound_email"]
