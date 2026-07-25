"""Integration tests for the Twilio SMS outbound path.

Uses respx to intercept httpx calls to Twilio's REST API. Tests
assert the URL, HTTP Basic auth header, form-encoded body shape,
and the message-SID round-trip stamping on ``messages.source_id``.

Anchors:
  reference/chatwoot/app/services/twilio/send_on_twilio_service.rb
  reference/chatwoot/app/models/channel/twilio_sms.rb
"""

from __future__ import annotations

import base64

import httpx
import pytest
import respx

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.inboxes.models import Inbox, TwilioSmsChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.twilio.sender import send_sms_twilio
from app.domains.users.models import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
async def _seed(
    db_session,
    *,
    suffix: str,
    contact_phone: str = "+15551234567",
    account_sid: str = "AC0123456789",
    auth_token: str = "atok-secret",
    phone_number: str = "+15559876543",
    api_key_sid: str | None = None,
    messaging_service_sid: str | None = None,
) -> tuple[TwilioSmsChannel, Inbox, Conversation, User]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@twout.example.com",
            account_name=f"TwOut{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    params: dict[str, object] = {
        "account_sid": account_sid,
        "auth_token": auth_token,
    }
    if phone_number:
        params["phone_number"] = phone_number
    if api_key_sid:
        params["api_key_sid"] = api_key_sid
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

    contact = Contact(
        account_id=owner.account.id,
        phone_number=contact_phone,
        name="Diana",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=result.inbox,
        source_id=contact_phone,
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    return result.channel, result.inbox, conv, owner.user


def _expected_url(channel: TwilioSmsChannel) -> str:
    return (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{channel.account_sid}/Messages.json"
    )


def _basic_auth_b64(user: str, password: str) -> str:
    return base64.b64encode(f"{user}:{password}".encode("ascii")).decode("ascii")


# ---------------------------------------------------------------------------
# send_sms_twilio — direct
# ---------------------------------------------------------------------------
@respx.mock
async def test_send_text_posts_to_twilio_with_basic_auth(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-shape")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="hi via Twilio",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            201,
            json={
                "sid": "SMxxxxxxxx",
                "status": "queued",
                "to": "+15551234567",
                "from": channel.phone_number,
            },
        )
    )
    ok = await send_sms_twilio(
        db_session, channel=channel, message=msg, to_phone="+15551234567"
    )
    assert ok is True

    request = route.calls.last.request
    expected_auth = f"Basic {_basic_auth_b64(channel.account_sid, channel.auth_token)}"
    assert request.headers.get("authorization") == expected_auth

    # Form-encoded body — Twilio requires this exact content-type.
    assert "application/x-www-form-urlencoded" in (
        request.headers.get("content-type") or ""
    )
    body = dict(part.split("=", 1) for part in request.content.decode().split("&"))
    # urllib quotes ``+`` as ``%2B``.
    assert body["To"] == "%2B15551234567"
    assert body["Body"] == "hi+via+Twilio"
    assert body["From"] == channel.phone_number.replace("+", "%2B")
    assert "MessagingServiceSid" not in body

    await db_session.refresh(msg)
    assert msg.source_id == "SMxxxxxxxx"


@respx.mock
async def test_send_text_uses_messaging_service_when_set(db_session):
    """``MessagingServiceSid`` takes precedence over the channel's
    ``phone_number`` for the From-side of the request — mirrors
    Channel::TwilioSms#send_message_from."""
    channel, inbox, conv, user = await _seed(
        db_session,
        suffix="-msvc",
        phone_number="+15551111111",
        messaging_service_sid="MGabcdef",
    )
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="msg",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            201,
            json={"sid": "SM-msvc"},
        )
    )
    ok = await send_sms_twilio(
        db_session, channel=channel, message=msg, to_phone="+15554443333"
    )
    assert ok is True
    body = dict(
        part.split("=", 1)
        for part in route.calls.last.request.content.decode().split("&")
    )
    assert body["MessagingServiceSid"] == "MGabcdef"
    assert "From" not in body


@respx.mock
async def test_send_text_uses_api_key_basic_auth_when_set(db_session):
    """When ``api_key_sid`` is configured, Basic auth pairs
    ``(api_key_sid, auth_token)`` instead of
    ``(account_sid, auth_token)``. Same as the Twilio Ruby gem."""
    channel, inbox, conv, user = await _seed(
        db_session,
        suffix="-apikey",
        api_key_sid="SKabcdef",
        auth_token="apikey-secret",
    )
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="hi",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(201, json={"sid": "SM-key"})
    )
    ok = await send_sms_twilio(
        db_session, channel=channel, message=msg, to_phone="+15551112222"
    )
    assert ok is True
    expected = f"Basic {_basic_auth_b64('SKabcdef', 'apikey-secret')}"
    assert route.calls.last.request.headers.get("authorization") == expected


@respx.mock
async def test_send_text_4xx_returns_false_no_stamp(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-fail")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="will fail",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()
    pre = msg.source_id

    respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            401,
            json={"code": 20003, "message": "Authenticate"},
        )
    )
    ok = await send_sms_twilio(
        db_session, channel=channel, message=msg, to_phone="+15551112222"
    )
    assert ok is False
    await db_session.refresh(msg)
    assert msg.source_id == pre


@respx.mock
async def test_send_text_skips_when_no_to_phone(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-noto")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="x",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(500)
    )
    ok = await send_sms_twilio(
        db_session, channel=channel, message=msg, to_phone=""
    )
    assert ok is False
    assert not route.called


# ---------------------------------------------------------------------------
# Full create_message cascade
# ---------------------------------------------------------------------------
@respx.mock
async def test_outgoing_via_create_message_hits_twilio(db_session):
    """Creating an outgoing Message on a Channel::TwilioSms inbox via
    create_message triggers Twilio send through the post-create
    cascade. The recipient phone resolves from
    ContactInbox.source_id."""
    channel, _inbox, conv, user = await _seed(
        db_session, suffix="-cascade", contact_phone="+15551234567"
    )

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(201, json={"sid": "SM-cascade"})
    )
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="from cascade",
            message_type="outgoing",
        ),
        user_id=user.id,
    )
    assert msg is not None
    assert route.called
    body = dict(
        part.split("=", 1)
        for part in route.calls.last.request.content.decode().split("&")
    )
    assert body["To"] == "%2B15551234567"
    assert body["Body"] == "from+cascade"
    await db_session.refresh(msg)
    assert msg.source_id == "SM-cascade"
