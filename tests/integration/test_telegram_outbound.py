"""Integration tests for the Telegram outbound path.

Uses respx to intercept httpx calls to ``api.telegram.org``. Tests
assert the URL, JSON body shape, ``reply_to_message_id`` plumbing,
and the ``message_id`` round-trip stamping on ``messages.source_id``.

Anchors:
  reference/chatwoot/app/services/telegram/send_on_telegram_service.rb
  reference/chatwoot/app/models/channel/telegram.rb
"""

from __future__ import annotations

import json

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
from app.domains.inboxes.models import Inbox, TelegramChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.telegram.sender import send_text_telegram
from app.domains.users.models import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
async def _seed(
    db_session,
    *,
    suffix: str,
    bot_token: str = "111:OUT-AAA",
    chat_id: int = 4242,
    tg_user_id: str = "TG-OUT-USER",
) -> tuple[TelegramChannel, Inbox, Conversation, User]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@tgout.example.com",
            account_name=f"TGOut{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="TG Inbox",
            channel_type="telegram",
            channel_params={"bot_token": bot_token, "bot_name": "AcmeBot"},
        ),
    ).perform()
    assert isinstance(result.channel, TelegramChannel)

    contact = Contact(account_id=owner.account.id, name="Diana")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=result.inbox,
        source_id=tg_user_id,
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(
            additional_attributes={"chat_id": chat_id},
        ),
    )
    return result.channel, result.inbox, conv, owner.user


def _expected_url(channel: TelegramChannel) -> str:
    return f"https://api.telegram.org/bot{channel.bot_token}/sendMessage"


# ---------------------------------------------------------------------------
# send_text_telegram — direct
# ---------------------------------------------------------------------------
@respx.mock
async def test_send_text_posts_canonical_body(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-shape")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="hi from Chatwoot via TG",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 7777, "text": "hi"}},
        )
    )
    ok = await send_text_telegram(
        db_session, channel=channel, message=msg, chat_id=4242
    )
    assert ok is True
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "chat_id": 4242,
        "text": "hi from Chatwoot via TG",
    }
    await db_session.refresh(msg)
    assert msg.source_id == "7777"


@respx.mock
async def test_send_text_includes_reply_to_message_id(db_session):
    """When ``content_attributes.in_reply_to_external_id`` is present,
    the sender threads it through Bot API's ``reply_to_message_id``."""
    channel, inbox, conv, user = await _seed(db_session, suffix="-reply")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="quoting you",
        sender_type="User",
        sender_id=user.id,
        private=False,
        content_attributes={"in_reply_to_external_id": "55"},
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 9, "text": "x"}},
        )
    )
    ok = await send_text_telegram(
        db_session, channel=channel, message=msg, chat_id=4242
    )
    assert ok is True
    body = json.loads(route.calls.last.request.content)
    assert body["reply_to_message_id"] == 55
    assert body["chat_id"] == 4242
    assert body["text"] == "quoting you"


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
            403,
            json={
                "ok": False,
                "error_code": 403,
                "description": "Forbidden: bot was blocked by the user",
            },
        )
    )
    ok = await send_text_telegram(
        db_session, channel=channel, message=msg, chat_id=4242
    )
    assert ok is False
    await db_session.refresh(msg)
    assert msg.source_id == pre


@respx.mock
async def test_send_text_bot_error_payload_returns_false(db_session):
    """A 200 with ``ok: false`` is still a Bot API failure (e.g. chat not
    found) — sender must not stamp source_id."""
    channel, inbox, conv, user = await _seed(db_session, suffix="-boterr")
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

    respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={"ok": False, "description": "chat not found"},
        )
    )
    ok = await send_text_telegram(
        db_session, channel=channel, message=msg, chat_id=4242
    )
    assert ok is False
    await db_session.refresh(msg)
    assert msg.source_id is None


@respx.mock
async def test_send_text_skips_when_missing_chat_id(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-noid")
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
    ok = await send_text_telegram(
        db_session, channel=channel, message=msg, chat_id=""
    )
    assert ok is False
    assert not route.called


# ---------------------------------------------------------------------------
# Full create_message cascade
# ---------------------------------------------------------------------------
@respx.mock
async def test_outgoing_message_via_create_message_hits_bot_api(db_session):
    """Creating an outgoing Message on a Channel::Telegram inbox via
    create_message triggers the Bot API send through the post-create
    cascade. The chat_id resolves from
    ``conversation.additional_attributes['chat_id']``."""
    channel, _inbox, conv, user = await _seed(
        db_session,
        suffix="-cascade",
        bot_token="222:CASCADE",
        chat_id=84848,
    )
    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 12345, "text": "x"}},
        )
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
    body = json.loads(route.calls.last.request.content)
    assert body["chat_id"] == 84848
    assert body["text"] == "from cascade"
    await db_session.refresh(msg)
    assert msg.source_id == "12345"


@respx.mock
async def test_private_note_does_not_hit_bot_api(db_session):
    """Private notes never leave Chatwoot. The cascade must not send
    them upstream."""
    channel, _inbox, conv, user = await _seed(
        db_session, suffix="-priv", bot_token="333:PRIV"
    )
    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(500)
    )
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="don't send me",
            message_type="outgoing",
            private=True,
        ),
        user_id=user.id,
    )
    assert msg is not None
    assert not route.called


@respx.mock
async def test_cascade_skips_when_chat_id_missing(db_session):
    """Conversations missing the inbound-stamped chat_id (e.g. seeded by
    pre-5g.2 code paths) short-circuit cleanly."""
    channel, _inbox, conv, user = await _seed(
        db_session, suffix="-nochat", bot_token="444:NOC"
    )
    # Wipe the chat_id stamped by the fixture.
    conv.additional_attributes = {}
    db_session.add(conv)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(500)
    )
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="orphan",
            message_type="outgoing",
        ),
        user_id=user.id,
    )
    assert msg is not None
    assert not route.called
