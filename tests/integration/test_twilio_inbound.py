"""Integration tests for the Twilio SMS webhook + inbound processor.

Twilio's webhook payload is form-encoded
(``application/x-www-form-urlencoded``). httpx's ``data=`` parameter
sends form-encoded by default, so we don't need a special helper.

Anchors:
  reference/chatwoot/app/services/twilio/incoming_message_service.rb
  reference/chatwoot/app/controllers/twilio/callback_controller.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    Conversation,
    Message,
)
from app.domains.inboxes.models import (
    Inbox,
    TwilioSmsChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.twilio.incoming import process_twilio_webhook
from app.main import app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
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


async def _seed(
    db_session,
    *,
    account_sid: str = "AC1234567890",
    phone_number: str = "+15551234567",
    suffix: str = "",
    messaging_service_sid: str | None = None,
) -> tuple[TwilioSmsChannel, Inbox]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@tw.example.com",
            account_name=f"TW{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    params: dict[str, object] = {
        "account_sid": account_sid,
        "auth_token": "atok",
        "phone_number": phone_number,
    }
    if messaging_service_sid:
        params["messaging_service_sid"] = messaging_service_sid
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Twilio Inbox",
            channel_type="twilio_sms",
            channel_params=params,
        ),
    ).perform()
    assert isinstance(result.channel, TwilioSmsChannel)
    return result.channel, result.inbox


# ---------------------------------------------------------------------------
# Inbound processor — direct
# ---------------------------------------------------------------------------
async def test_text_creates_contact_and_conversation(db_session):
    channel, _inbox = await _seed(db_session, suffix="-text")
    msg = await process_twilio_webhook(
        db_session,
        params={
            "AccountSid": "AC1234567890",
            "To": "+15551234567",
            "From": "+15559998888",
            "Body": "hi from twilio",
            "SmsSid": "SM-aaa-1",
            "MessageSid": "SM-aaa-1",
        },
    )
    assert msg is not None
    assert msg.message_type == MESSAGE_TYPE_INCOMING
    assert msg.content == "hi from twilio"
    assert msg.source_id == "SM-aaa-1"

    contact = (
        await db_session.exec(
            select(Contact).where(
                Contact.phone_number == "+15559998888"
            )
        )
    ).first()
    assert contact is not None
    ci = (
        await db_session.exec(
            select(ContactInbox).where(
                ContactInbox.contact_id == contact.id
            )
        )
    ).first()
    assert ci is not None
    assert ci.source_id == "+15559998888"


async def test_resolves_channel_by_messaging_service_sid_first(db_session):
    """``MessagingServiceSid`` takes precedence over ``(AccountSid, To)``.
    Even when the AccountSid+To pair would resolve a different channel,
    MessagingServiceSid wins."""
    # Channel A: phone-only.
    channel_a, _ = await _seed(
        db_session,
        suffix="-msvc-a",
        account_sid="ACphone",
        phone_number="+15551111111",
    )
    # Channel B: messaging-service.
    channel_b, _ = await _seed(
        db_session,
        suffix="-msvc-b",
        account_sid="ACmsvc",
        phone_number="+15552222222",
        messaging_service_sid="MGxxxx",
    )

    msg = await process_twilio_webhook(
        db_session,
        params={
            "AccountSid": "ACphone",  # would match A on (sid, to)
            "To": "+15551111111",
            "From": "+15559876543",
            "Body": "hi",
            "SmsSid": "SM-msvc",
            "MessagingServiceSid": "MGxxxx",
        },
    )
    assert msg is not None
    assert msg.inbox_id != channel_a.id
    assert msg.account_id == channel_b.account_id


async def test_unknown_account_drops_silently(db_session):
    await _seed(db_session, suffix="-unknown")
    msg = await process_twilio_webhook(
        db_session,
        params={
            "AccountSid": "ACdoesnotexist",
            "To": "+19999999999",
            "From": "+15559998888",
            "Body": "hi",
            "SmsSid": "SM-x",
        },
    )
    assert msg is None


async def test_duplicate_sms_sid_is_idempotent(db_session):
    await _seed(db_session, suffix="-dup")
    payload = {
        "AccountSid": "AC1234567890",
        "To": "+15551234567",
        "From": "+15554443333",
        "Body": "once",
        "SmsSid": "SM-dup",
    }
    first = await process_twilio_webhook(db_session, params=payload)
    second = await process_twilio_webhook(db_session, params=payload)
    assert first is not None
    assert second is None


async def test_two_messages_share_conversation(db_session):
    """SMS threads are durable per-(number, inbox) — two events on
    the same number land on the same conversation."""
    await _seed(db_session, suffix="-thread")
    base = {
        "AccountSid": "AC1234567890",
        "To": "+15551234567",
        "From": "+15557776666",
    }
    await process_twilio_webhook(
        db_session,
        params={**base, "SmsSid": "SM-1", "Body": "first"},
    )
    await process_twilio_webhook(
        db_session,
        params={**base, "SmsSid": "SM-2", "Body": "second"},
    )
    convs = list((await db_session.exec(select(Conversation))).all())
    assert len(convs) == 1


async def test_missing_from_drops_silently(db_session):
    await _seed(db_session, suffix="-nofrom")
    msg = await process_twilio_webhook(
        db_session,
        params={
            "AccountSid": "AC1234567890",
            "To": "+15551234567",
            "Body": "no from",
            "SmsSid": "SM-nofrom",
        },
    )
    assert msg is None


# ---------------------------------------------------------------------------
# HTTP form-encoded webhook end-to-end
# ---------------------------------------------------------------------------
async def test_webhook_accepts_form_encoded_body(client, db_session):
    """End-to-end: HTTP POST with form-encoded body lands a Message."""
    await _seed(db_session, suffix="-http")
    resp = await client.post(
        "/twilio/callback",
        data={
            "AccountSid": "AC1234567890",
            "To": "+15551234567",
            "From": "+15551112222",
            "Body": "via http",
            "SmsSid": "SM-http",
            "MessageSid": "SM-http",
        },
    )
    assert resp.status_code == 200
    msg = (
        await db_session.exec(
            select(Message).where(Message.source_id == "SM-http")
        )
    ).first()
    assert msg is not None
    assert msg.content == "via http"


async def test_webhook_unknown_account_still_200s(client):
    """Unknown account drops the payload silently but ALWAYS 200 —
    Twilio retries on 5xx."""
    resp = await client.post(
        "/twilio/callback",
        data={
            "AccountSid": "ACnope",
            "To": "+19999999999",
            "From": "+15551234567",
            "Body": "hi",
            "SmsSid": "SM-x",
        },
    )
    assert resp.status_code == 200
