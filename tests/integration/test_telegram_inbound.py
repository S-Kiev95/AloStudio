"""Integration tests for the Telegram webhook + inbound processor.

Anchors:
  reference/chatwoot/app/services/telegram/incoming_message_service.rb
  reference/chatwoot/app/services/telegram/param_helpers.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

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
    TelegramChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.telegram.incoming import process_telegram_webhook
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
    bot_token: str = "111:AAA",
    suffix: str = "",
) -> tuple[TelegramChannel, Inbox]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@tg-in.example.com",
            account_name=f"TGIn{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme TG",
            channel_type="telegram",
            channel_params={"bot_token": bot_token, "bot_name": "AcmeBot"},
        ),
    ).perform()
    assert isinstance(result.channel, TelegramChannel)
    return result.channel, result.inbox


def _msg_payload(
    *,
    user_id: int,
    chat_id: int,
    message_id: int,
    text: str,
    first_name: str = "Diana",
    chat_type: str = "private",
    reply_to_message_id: int | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "message_id": message_id,
        "from": {
            "id": user_id,
            "is_bot": False,
            "first_name": first_name,
            "username": "diana",
            "language_code": "en",
        },
        "chat": {
            "id": chat_id,
            "first_name": first_name,
            "username": "diana",
            "type": chat_type,
        },
        "date": 1700000000,
        "text": text,
    }
    if reply_to_message_id is not None:
        message["reply_to_message"] = {"message_id": reply_to_message_id}
    return {"update_id": 999, "message": message}


# ---------------------------------------------------------------------------
# Inbound processor
# ---------------------------------------------------------------------------
async def test_text_creates_contact_and_conversation(db_session):
    _channel, _inbox = await _seed(
        db_session, bot_token="aa:1", suffix="-text"
    )
    msg = await process_telegram_webhook(
        db_session,
        bot_token="aa:1",
        payload=_msg_payload(
            user_id=12345, chat_id=67890, message_id=1, text="hi from tg"
        ),
    )
    assert msg is not None
    assert msg.message_type == MESSAGE_TYPE_INCOMING
    assert msg.content == "hi from tg"
    # source_id is chat-composite ("{chat_id}.{message_id}") so the
    # dedup is unique per chat — Telegram message_ids only count within
    # a chat, not globally.
    assert msg.source_id == "67890.1"

    ci = (
        await db_session.exec(
            select(ContactInbox).where(ContactInbox.source_id == "12345")
        )
    ).first()
    assert ci is not None
    contact = await db_session.get(Contact, ci.contact_id)
    assert contact is not None
    assert contact.name == "Diana"

    conv = await db_session.get(Conversation, msg.conversation_id)
    assert conv is not None
    assert (conv.additional_attributes or {}).get("chat_id") == 67890


async def test_unknown_bot_token_drops_silently(db_session):
    await _seed(db_session, bot_token="known:1", suffix="-bad")
    msg = await process_telegram_webhook(
        db_session,
        bot_token="unknown:999",
        payload=_msg_payload(
            user_id=1, chat_id=2, message_id=3, text="hi"
        ),
    )
    assert msg is None


async def test_group_chat_drops_silently(db_session):
    """Mirror Chatwoot — group / channel / supergroup chats drop
    silently. Only ``chat.type == 'private'`` proceeds."""
    await _seed(db_session, bot_token="grp:1", suffix="-grp")
    msg = await process_telegram_webhook(
        db_session,
        bot_token="grp:1",
        payload=_msg_payload(
            user_id=1,
            chat_id=2,
            message_id=3,
            text="hi",
            chat_type="group",
        ),
    )
    assert msg is None


async def test_duplicate_message_id_is_idempotent(db_session):
    await _seed(db_session, bot_token="dup:1", suffix="-dup")
    payload = _msg_payload(
        user_id=11, chat_id=22, message_id=33, text="once"
    )
    first = await process_telegram_webhook(
        db_session, bot_token="dup:1", payload=payload
    )
    second = await process_telegram_webhook(
        db_session, bot_token="dup:1", payload=payload
    )
    assert first is not None
    assert second is None


async def test_same_message_id_different_chats_both_ingested(db_session):
    """Regression: Telegram message_id is unique only within a chat, so
    two different users of the same bot routinely share message_id=1.
    The dedup must be chat-scoped (composite source_id) — both messages
    must land, not be dropped as false duplicates. Before the fix the
    second was silently lost."""
    await _seed(db_session, bot_token="coll:1", suffix="-coll")
    first = await process_telegram_webhook(
        db_session,
        bot_token="coll:1",
        payload=_msg_payload(
            user_id=111, chat_id=111, message_id=1, text="from user A"
        ),
    )
    second = await process_telegram_webhook(
        db_session,
        bot_token="coll:1",
        payload=_msg_payload(
            user_id=222, chat_id=222, message_id=1, text="from user B"
        ),
    )
    assert first is not None
    assert second is not None, (
        "second user's message dropped as false duplicate — dedup not "
        "chat-scoped"
    )
    assert first.source_id == "111.1"
    assert second.source_id == "222.1"
    assert first.content == "from user A"
    assert second.content == "from user B"
    # Distinct chats → distinct conversations.
    assert first.conversation_id != second.conversation_id


async def test_two_messages_share_conversation(db_session):
    await _seed(db_session, bot_token="thr:1", suffix="-thr")
    base_user = 100
    base_chat = 200
    await process_telegram_webhook(
        db_session,
        bot_token="thr:1",
        payload=_msg_payload(
            user_id=base_user, chat_id=base_chat, message_id=1, text="hi"
        ),
    )
    await process_telegram_webhook(
        db_session,
        bot_token="thr:1",
        payload=_msg_payload(
            user_id=base_user,
            chat_id=base_chat,
            message_id=2,
            text="anybody?",
        ),
    )
    convs = list((await db_session.exec(select(Conversation))).all())
    assert len(convs) == 1


async def test_reply_to_stamps_in_reply_to_external_id(db_session):
    """``reply_to_message.message_id`` -> stored under
    ``content_attributes.in_reply_to_external_id`` so the outbound
    sender can pass ``reply_to_message_id`` to ``sendMessage``."""
    await _seed(db_session, bot_token="rpl:1", suffix="-rpl")
    msg = await process_telegram_webhook(
        db_session,
        bot_token="rpl:1",
        payload=_msg_payload(
            user_id=1,
            chat_id=2,
            message_id=10,
            text="answering",
            reply_to_message_id=5,
        ),
    )
    assert msg is not None
    assert (msg.content_attributes or {}).get("in_reply_to_external_id") == "5"


async def test_caption_falls_back_to_text(db_session):
    """When a Telegram message arrives with media (caption only, no
    text), our processor reads ``caption`` as the body."""
    await _seed(db_session, bot_token="cap:1", suffix="-cap")
    payload = _msg_payload(
        user_id=1, chat_id=2, message_id=4, text=""
    )
    payload["message"].pop("text")
    payload["message"]["caption"] = "captioned"
    msg = await process_telegram_webhook(
        db_session, bot_token="cap:1", payload=payload
    )
    assert msg is not None
    assert msg.content == "captioned"


# ---------------------------------------------------------------------------
# HTTP webhook end-to-end
# ---------------------------------------------------------------------------
async def test_webhook_accepts_json_payload(client, db_session):
    await _seed(db_session, bot_token="http:1", suffix="-http")
    body = _msg_payload(
        user_id=42, chat_id=84, message_id=99, text="via http"
    )
    resp = await client.post(
        "/webhooks/telegram/http:1",
        json=body,
    )
    assert resp.status_code == 200
    msg = (
        await db_session.exec(
            select(Message).where(Message.source_id == "84.99")
        )
    ).first()
    assert msg is not None
    assert msg.content == "via http"


async def test_webhook_unknown_token_still_200s(client):
    resp = await client.post(
        "/webhooks/telegram/unknown:99",
        json={"update_id": 1, "message": {"message_id": 1}},
    )
    assert resp.status_code == 200


async def test_webhook_malformed_body_still_200s(client):
    resp = await client.post(
        "/webhooks/telegram/anything",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
