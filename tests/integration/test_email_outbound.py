"""Integration tests for SMTP outbound on ``Channel::Email`` inboxes.

The mailer fires from the message-create post-create cascade — when
an outgoing message lands on an Email inbox with ``smtp_enabled``,
:func:`send_email_reply` builds the RFC-2822 envelope + sends via
SMTP + stamps the Message-ID on ``message.source_id`` so threading
works on the reply.

Anchors:
  reference/chatwoot/app/mailers/conversation_reply_mailer.rb
  reference/chatwoot/app/mailers/concerns/references_header_builder.rb
  app/domains/email/mailer.py

Greenmail provides the SMTP server. Tests reset its state per-test
so messages from one test never leak into another.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    Conversation,
    Message,
    MESSAGE_TYPE_OUTGOING,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
    create_message,
    MessageBuilderParams,
)
from app.domains.inboxes.models import EmailChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.main import app
from tests.integration import _greenmail

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_greenmail() -> None:
    """Drop every queued mail before each test so assertions are deterministic."""
    _greenmail.reset()


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _seed_email_inbox(
    db_session, *, smtp_enabled: bool = True
):
    """Account + Email inbox with Greenmail SMTP + a contact w/ email."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@em-out.example.com",
            account_name="EmOut",
            user_full_name="Em Out Admin",
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
                "email": "support@example.com",
                "smtp_enabled": smtp_enabled,
                "smtp_address": _greenmail.GREENMAIL_SMTP_HOST,
                "smtp_port": _greenmail.GREENMAIL_SMTP_PORT,
                "smtp_login": "support@example.com",
                "smtp_password": "ignored",  # auth disabled
                "smtp_enable_starttls_auto": False,
                "smtp_enable_ssl_tls": False,
            },
        ),
    ).perform()
    inbox = result.inbox
    channel = result.channel
    assert isinstance(channel, EmailChannel)

    contact = Contact(
        account_id=owner.account.id,
        email="alice@example.com",
        name="Alice",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox
    ).perform()
    return owner, inbox, channel, contact, ci


async def _create_outbound(
    db_session, *, ci, content: str, user_id: int
) -> tuple[Conversation, Message]:
    """Create a fresh conversation + outbound message via the service layer."""
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content=content,
            message_type="outgoing",
        ),
        user_id=user_id,
    )
    return conv, msg


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
async def test_outgoing_message_sends_email_via_smtp(client, db_session):
    """An outgoing message on an Email inbox lands in Greenmail with
    sane From/To/Subject/Date headers."""
    owner, _, channel, contact, ci = await _seed_email_inbox(db_session)
    conv, msg = await _create_outbound(
        db_session, ci=ci, content="Thanks for reaching out!", user_id=owner.user.id
    )

    received = _greenmail.messages_for(contact.email)
    assert len(received) == 1, received
    raw = received[0]["mimeMessage"]
    assert "From: " in raw
    assert "support@example.com" in raw
    assert f"To: " in raw
    assert "alice@example.com" in raw
    assert "Thanks for reaching out!" in raw


async def test_message_id_is_stamped_on_source_id(client, db_session):
    """The Message-ID header value (without angle brackets) is written
    to ``message.source_id`` so the threading lookup hits it on the
    inbound reply."""
    owner, _, channel, contact, ci = await _seed_email_inbox(db_session)
    conv, msg = await _create_outbound(
        db_session, ci=ci, content="hi", user_id=owner.user.id
    )

    await db_session.refresh(msg)
    assert msg.source_id is not None
    # Format mirrors Chatwoot:
    #   conversation/<uuid>/messages/<msg_id>@<channel-domain>
    assert "conversation/" in msg.source_id
    assert f"messages/{msg.id}@example.com" in msg.source_id

    # That same Message-ID must appear in the headers Greenmail received.
    raw = _greenmail.messages_for(contact.email)[0]["mimeMessage"]
    assert msg.source_id in raw  # bare value sits inside <...>


async def test_in_reply_to_root_when_no_inbound(client, db_session):
    """Without an inbound message yet, In-Reply-To points at the
    synthetic per-conversation root."""
    owner, _, channel, contact, ci = await _seed_email_inbox(db_session)
    conv, msg = await _create_outbound(
        db_session, ci=ci, content="agent-initiated", user_id=owner.user.id
    )

    raw = _greenmail.messages_for(contact.email)[0]["mimeMessage"]
    # Long headers ($value > 78 chars) get folded to a continuation line
    # per RFC-2822, so we assert on the bracketed value rather than the
    # ``Header: value`` form.
    expected = f"<account/{conv.account_id}/conversation/{conv.uuid}@example.com>"
    assert expected in raw, f"\nEXPECTED:\n{expected}\n\nRAW:\n{raw}"
    # Sanity: the In-Reply-To header name is present (folded or not).
    assert "In-Reply-To:" in raw


async def test_subject_uses_default_when_no_mail_subject(
    client, db_session
):
    """Default subject is ``[#<display_id>] New messages on this conversation``."""
    owner, _, channel, contact, ci = await _seed_email_inbox(db_session)
    conv, msg = await _create_outbound(
        db_session, ci=ci, content="hi", user_id=owner.user.id
    )

    raw = _greenmail.messages_for(contact.email)[0]["mimeMessage"]
    assert f"Subject: [#{conv.display_id}] New messages on this conversation" in raw


async def test_subject_uses_re_prefix_on_reply(client, db_session):
    """When the conversation has a stored ``mail_subject`` AND there's
    already at least one message, the outbound uses ``Re: <subject>``."""
    owner, _, channel, contact, ci = await _seed_email_inbox(db_session)
    # Seed a conversation with a stored mail_subject + one prior message.
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(
            additional_attributes={"mail_subject": "Account billing question"},
        ),
    )
    # Drop a prior incoming message via direct insert so the chat count is 1
    # before the outbound lands.
    from app.domains.conversations.models import (
        CONTENT_TYPE_TEXT,
        MESSAGE_TYPE_INCOMING,
    )

    incoming = Message(
        account_id=conv.account_id,
        inbox_id=conv.inbox_id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_INCOMING,
        content_type=CONTENT_TYPE_TEXT,
        content="Initial mail",
        sender_type="Contact",
        sender_id=contact.id,
        private=False,
        content_attributes={
            "email": {"message_id": "external-original@client.example.com"}
        },
    )
    db_session.add(incoming)
    await db_session.flush()

    # Now post the outbound — chat count becomes 2 → Re: prefix.
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="Got it, looking into it.",
            message_type="outgoing",
        ),
        user_id=owner.user.id,
    )

    raw = _greenmail.messages_for(contact.email)[0]["mimeMessage"]
    assert "Subject: Re: Account billing question" in raw
    # In-Reply-To should now point at the inbound message-id (with brackets).
    # The header may fold across lines per RFC-2822; assert on value only.
    assert "<external-original@client.example.com>" in raw
    assert "In-Reply-To:" in raw


# ---------------------------------------------------------------------------
# Skip branches
# ---------------------------------------------------------------------------
async def test_skipped_when_smtp_disabled(client, db_session):
    owner, _, channel, contact, ci = await _seed_email_inbox(
        db_session, smtp_enabled=False
    )
    await _create_outbound(
        db_session, ci=ci, content="hi", user_id=owner.user.id
    )
    assert _greenmail.messages_for(contact.email) == []


async def test_skipped_when_contact_has_no_email(client, db_session):
    """A contact without an email address can't be the recipient — the
    mailer logs + skips. Mirrors Rails' ``return unless to_emails.compact``."""
    owner, _, channel, contact, ci = await _seed_email_inbox(db_session)
    contact.email = None
    db_session.add(contact)
    await db_session.flush()

    await _create_outbound(
        db_session, ci=ci, content="hi", user_id=owner.user.id
    )
    # Greenmail saw nothing addressed to alice (the now-empty contact).
    # We assert across all queued mail to be safe.
    # (Greenmail's "messages by user" requires a known recipient; we
    #  lean on the SMTP send simply not happening — the message row
    #  has no source_id stamp.)
    msg = (await db_session.exec(select(Message))).first()
    assert msg is not None
    assert msg.source_id is None


async def test_skipped_for_private_message(client, db_session):
    """Private notes (``private=True``) are agent-only timeline entries
    — never sent as email."""
    owner, _, channel, contact, ci = await _seed_email_inbox(db_session)
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="internal note",
            message_type="outgoing",
            private=True,
        ),
        user_id=owner.user.id,
    )
    assert _greenmail.messages_for(contact.email) == []
    assert msg.source_id is None
