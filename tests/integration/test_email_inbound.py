"""Integration tests for IMAP ingest on ``Channel::Email`` inboxes.

Two layers:
  * :func:`process_inbound_email` — given a parsed :class:`Email
    Message` + a Channel, creates Contact + ContactInbox + Conversation
    + Message rows. Tested directly with hand-built mails so we can
    cover threading edges without orchestrating SMTP.
  * :func:`fetch_inbox_once` — connects to Greenmail's IMAP server,
    pulls UNSEEN, hands off to ``process_inbound_email``. Tests inject
    mail by sending it through Greenmail's SMTP, then run the fetcher.

Anchors:
  reference/chatwoot/app/services/imap/imap_mailbox.rb
  reference/chatwoot/app/services/imap/fetch_email_service.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from email.message import EmailMessage

import aiosmtplib
import pytest
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import (
    Conversation,
    Message,
    MESSAGE_TYPE_INCOMING,
)
from app.domains.email.imap_fetch import fetch_inbox_once
from app.domains.email.inbound import process_inbound_email
from app.domains.inboxes.models import EmailChannel, Inbox
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
# Imported only so the SQLAlchemy mapper resolves Conversation.team
# before the first DB op. See note in app/domains/labels/models.py.
from app.domains.teams import models as _teams  # noqa: F401
from tests.integration import _greenmail

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_greenmail() -> None:
    _greenmail.reset()


async def _seed_email_inbox(
    db_session,
    *,
    inbox_email: str = "support@example.com",
    suffix: str = "",
    imap_enabled: bool = True,
) -> tuple[Inbox, EmailChannel]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@em-in.example.com",
            account_name=f"EmIn{suffix}",
            user_full_name=f"Em In Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Support",
            channel_type="email",
            channel_params={
                "email": inbox_email,
                "imap_enabled": imap_enabled,
                "imap_address": _greenmail.GREENMAIL_IMAP_HOST,
                "imap_port": _greenmail.GREENMAIL_IMAP_PORT,
                "imap_login": inbox_email,
                "imap_password": "ignored",
                "imap_enable_ssl": False,
            },
        ),
    ).perform()
    assert isinstance(result.channel, EmailChannel)
    return result.inbox, result.channel


def _build_mail(
    *,
    sender: str,
    sender_name: str | None,
    to: str,
    subject: str,
    body: str,
    message_id: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> EmailMessage:
    mail = EmailMessage()
    if sender_name:
        mail["From"] = f"{sender_name} <{sender}>"
    else:
        mail["From"] = sender
    mail["To"] = to
    mail["Subject"] = subject
    if message_id:
        mail["Message-ID"] = (
            message_id if message_id.startswith("<") else f"<{message_id}>"
        )
    if in_reply_to:
        mail["In-Reply-To"] = (
            in_reply_to if in_reply_to.startswith("<") else f"<{in_reply_to}>"
        )
    if references:
        mail["References"] = references
    mail.set_content(body)
    return mail


# ---------------------------------------------------------------------------
# process_inbound_email — pure ingest unit (no IMAP)
# ---------------------------------------------------------------------------
async def test_process_creates_contact_conversation_and_message(db_session):
    inbox, channel = await _seed_email_inbox(db_session)

    mail = _build_mail(
        sender="alice@external.example.com",
        sender_name="Alice",
        to="support@example.com",
        subject="My account is locked",
        body="Please help me regain access.",
        message_id="external-1@client.example.com",
    )
    msg = await process_inbound_email(
        db_session, channel=channel, inbox=inbox, mail=mail
    )
    assert msg is not None
    assert msg.message_type == MESSAGE_TYPE_INCOMING
    assert msg.content.strip() == "Please help me regain access."
    assert msg.source_id == "external-1@client.example.com"
    # content_attributes carries the email metadata so the outbound
    # mailer can reference it on a reply.
    email_meta = (msg.content_attributes or {}).get("email", {})
    assert email_meta.get("message_id") == "external-1@client.example.com"

    # Contact was minted with the from-address as email.
    contact = (
        await db_session.exec(
            select(Contact).where(Contact.email == "alice@external.example.com")
        )
    ).first()
    assert contact is not None
    assert contact.name == "Alice"

    # Conversation tagged with the subject line via additional_attributes.
    conv = await db_session.get(Conversation, msg.conversation_id)
    assert conv is not None
    assert (conv.additional_attributes or {}).get("mail_subject") == "My account is locked"


async def test_process_threads_reply_under_existing_conversation(db_session):
    """A reply whose ``In-Reply-To`` matches a stamped message-id lands
    on the SAME conversation as the original."""
    inbox, channel = await _seed_email_inbox(db_session, suffix="-thread")

    # First mail: starts a conversation.
    first = _build_mail(
        sender="alice@external.example.com",
        sender_name="Alice",
        to="support@example.com",
        subject="Help!",
        body="please",
        message_id="root-1@client.example.com",
    )
    first_msg = await process_inbound_email(
        db_session, channel=channel, inbox=inbox, mail=first
    )
    assert first_msg is not None

    # Second mail: a reply (In-Reply-To = the first's Message-ID).
    reply = _build_mail(
        sender="alice@external.example.com",
        sender_name="Alice",
        to="support@example.com",
        subject="Re: Help!",
        body="any update?",
        message_id="reply-1@client.example.com",
        in_reply_to="root-1@client.example.com",
        references="<root-1@client.example.com>",
    )
    reply_msg = await process_inbound_email(
        db_session, channel=channel, inbox=inbox, mail=reply
    )
    assert reply_msg is not None
    assert reply_msg.conversation_id == first_msg.conversation_id


async def test_process_skips_duplicate_message_id(db_session):
    """Same Message-ID twice → the second insert is dropped (idempotent
    ingest). Mirrors ``Message.find_by(source_id:)`` short-circuit."""
    inbox, channel = await _seed_email_inbox(db_session, suffix="-dup")
    mail = _build_mail(
        sender="bob@external.example.com",
        sender_name="Bob",
        to="support@example.com",
        subject="hello",
        body="hi",
        message_id="dup-1@client.example.com",
    )
    first = await process_inbound_email(
        db_session, channel=channel, inbox=inbox, mail=mail
    )
    second = await process_inbound_email(
        db_session, channel=channel, inbox=inbox, mail=mail
    )
    assert first is not None
    assert second is None
    # Only one message row exists.
    rows = list(
        (
            await db_session.exec(
                select(Message).where(Message.source_id == "dup-1@client.example.com")
            )
        ).all()
    )
    assert len(rows) == 1


async def test_process_skips_when_from_unparseable(db_session):
    inbox, channel = await _seed_email_inbox(db_session, suffix="-nofrom")
    mail = EmailMessage()
    mail["Subject"] = "no from header"
    mail.set_content("orphan")
    msg = await process_inbound_email(
        db_session, channel=channel, inbox=inbox, mail=mail
    )
    assert msg is None


async def test_process_reuses_existing_contact_by_email(db_session):
    """A second mail from the same address reuses the contact +
    contact_inbox — the source_id stays the email address."""
    inbox, channel = await _seed_email_inbox(db_session, suffix="-reuse")
    for n in range(2):
        await process_inbound_email(
            db_session,
            channel=channel,
            inbox=inbox,
            mail=_build_mail(
                sender="carol@external.example.com",
                sender_name="Carol",
                to="support@example.com",
                subject=f"hi-{n}",
                body=f"msg-{n}",
                message_id=f"unique-{n}@client.example.com",
            ),
        )
    contacts = list(
        (
            await db_session.exec(
                select(Contact).where(
                    Contact.email == "carol@external.example.com"
                )
            )
        ).all()
    )
    assert len(contacts) == 1
    cis = list(
        (
            await db_session.exec(
                select(ContactInbox).where(
                    ContactInbox.contact_id == contacts[0].id,
                    ContactInbox.inbox_id == inbox.id,
                )
            )
        ).all()
    )
    assert len(cis) == 1


# ---------------------------------------------------------------------------
# fetch_inbox_once — IMAP transport via Greenmail
# ---------------------------------------------------------------------------
async def test_fetch_pulls_unseen_messages_via_imap(db_session):
    inbox, channel = await _seed_email_inbox(db_session, suffix="-imap")

    # Drop a mail into Greenmail addressed to the inbox via SMTP.
    mail = EmailMessage()
    mail["From"] = "Diane <diane@external.example.com>"
    mail["To"] = "support@example.com"
    mail["Subject"] = "imap roundtrip"
    mail["Message-ID"] = "<imap-1@client.example.com>"
    mail.set_content("delivered via imap")
    await aiosmtplib.send(
        mail,
        hostname=_greenmail.GREENMAIL_SMTP_HOST,
        port=_greenmail.GREENMAIL_SMTP_PORT,
    )

    ingested = await fetch_inbox_once(
        db_session, channel=channel, inbox=inbox
    )
    assert ingested == 1

    msg = (
        await db_session.exec(
            select(Message).where(Message.source_id == "imap-1@client.example.com")
        )
    ).first()
    assert msg is not None
    assert msg.message_type == MESSAGE_TYPE_INCOMING
    assert "delivered via imap" in (msg.content or "")


async def test_fetch_marks_seen_so_second_run_is_noop(db_session):
    inbox, channel = await _seed_email_inbox(db_session, suffix="-seen")

    mail = EmailMessage()
    mail["From"] = "eve@external.example.com"
    mail["To"] = "support@example.com"
    mail["Subject"] = "once"
    mail["Message-ID"] = "<once-1@client.example.com>"
    mail.set_content("seen-flag check")
    await aiosmtplib.send(
        mail,
        hostname=_greenmail.GREENMAIL_SMTP_HOST,
        port=_greenmail.GREENMAIL_SMTP_PORT,
    )

    first = await fetch_inbox_once(
        db_session, channel=channel, inbox=inbox
    )
    second = await fetch_inbox_once(
        db_session, channel=channel, inbox=inbox
    )
    assert first == 1
    assert second == 0


async def test_fetch_short_circuits_when_imap_disabled(db_session):
    inbox, channel = await _seed_email_inbox(
        db_session, suffix="-noimap", imap_enabled=False
    )
    n = await fetch_inbox_once(db_session, channel=channel, inbox=inbox)
    assert n == 0
