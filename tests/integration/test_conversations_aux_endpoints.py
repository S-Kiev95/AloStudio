"""Integration tests for the Phase 4b.5 leftover endpoints:
``POST /conversations/:id/toggle_typing_status``,
``GET  /conversations/:id/attachments``,
``PATCH /conversations/:conv_id/messages/:id``.

Anchors:
  * ``ConversationsController#toggle_typing_status`` +
    ``Conversations::TypingStatusManager``.
  * ``ConversationsController#attachments`` + ``attachments.json.jbuilder``.
  * ``Api::V1::Accounts::Conversations::MessagesController#update`` +
    ``Messages::StatusUpdateService`` (read -> delivered is a no-op).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONTENT_TYPE_TEXT,
    FILE_TYPE_FILE,
    MESSAGE_STATUS_READ,
    MESSAGE_STATUS_SENT,
    MESSAGE_TYPE_OUTGOING,
    Attachment,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
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


async def _mint_headers(db_session, user) -> dict[str, str]:
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


async def _seed_api(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@aux.example.com",
            account_name="Aux Inc",
            user_full_name="Aux Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="API Inbox",
                channel_type="api",
                channel_params={"webhook_url": "https://example.com/h"},
            ),
        ).perform()
    ).inbox
    contact = Contact(
        account_id=owner.account.id,
        email="c@aux.example.com",
        name="Aux Contact",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox
    ).perform()
    headers = await _mint_headers(db_session, owner.user)
    return owner, inbox, contact, ci, headers


@pytest.fixture
async def seeded(db_session):
    return await _seed_api(db_session)


async def _make_conv(db_session, *, contact_inbox) -> Conversation:
    return await create_conversation(
        db_session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(),
    )


# ---------------------------------------------------------------------------
# toggle_typing_status
# ---------------------------------------------------------------------------
async def test_toggle_typing_status_returns_head_ok_for_on(client, seeded, db_session):
    owner, _, _, ci, headers = seeded
    conv = await _make_conv(db_session, contact_inbox=ci)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/toggle_typing_status",
        json={"typing_status": "on", "is_private": False},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.content == b""


async def test_toggle_typing_status_off(client, seeded, db_session):
    owner, _, _, ci, headers = seeded
    conv = await _make_conv(db_session, contact_inbox=ci)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/toggle_typing_status",
        json={"typing_status": "off"},
        headers=headers,
    )
    assert resp.status_code == 200


async def test_toggle_typing_status_unknown_status_is_noop(
    client, seeded, db_session
):
    """Mirrors Rails' case statement falling through silently."""
    owner, _, _, ci, headers = seeded
    conv = await _make_conv(db_session, contact_inbox=ci)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/toggle_typing_status",
        json={"typing_status": "maybe"},
        headers=headers,
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# attachments index
# ---------------------------------------------------------------------------
async def test_attachments_index_empty(client, seeded, db_session):
    owner, _, _, ci, headers = seeded
    conv = await _make_conv(db_session, contact_inbox=ci)
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/attachments",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"meta": {"total_count": 0}, "payload": []}


async def test_attachments_index_returns_message_attachments(
    client, seeded, db_session
):
    """Assert the wire shape mirrors ``attachments.json.jbuilder`` —
    ``meta.total_count`` + ``payload[]`` with message-derived created_at
    + sender block."""
    owner, _, _, ci, headers = seeded
    conv = await _make_conv(db_session, contact_inbox=ci)

    msg = Message(
        account_id=conv.account_id,
        inbox_id=conv.inbox_id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=CONTENT_TYPE_TEXT,
        content="Here you go",
        sender_type="User",
        sender_id=owner.user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    att = Attachment(
        account_id=conv.account_id,
        message_id=msg.id,
        file_type=FILE_TYPE_FILE,
        external_url="https://files.example.com/quote.pdf",
        coordinates_lat=0.0,
        coordinates_long=0.0,
    )
    db_session.add(att)
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/attachments",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["total_count"] == 1
    assert len(body["payload"]) == 1
    item = body["payload"][0]
    assert item["message_id"] == msg.id
    assert item["data_url"] == "https://files.example.com/quote.pdf"
    assert item["file_type"] == "file"
    assert "created_at" in item
    assert item["sender"]["id"] == owner.user.id


# ---------------------------------------------------------------------------
# messages#update — API inbox status flip
# ---------------------------------------------------------------------------
async def test_messages_update_status_sent_to_delivered(
    client, seeded, db_session
):
    owner, _, _, ci, headers = seeded
    conv = await _make_conv(db_session, contact_inbox=ci)
    msg = Message(
        account_id=conv.account_id,
        inbox_id=conv.inbox_id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=CONTENT_TYPE_TEXT,
        content="Hi",
        status=MESSAGE_STATUS_SENT,
        sender_type="User",
        sender_id=owner.user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages/{msg.id}",
        json={"status": "delivered"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == msg.id
    assert body["status"] == "delivered"


async def test_messages_update_read_to_delivered_is_silent_noop(
    client, seeded, db_session
):
    """Mirrors Rails' ``return false if message.read? && status == 'delivered'``."""
    owner, _, _, ci, headers = seeded
    conv = await _make_conv(db_session, contact_inbox=ci)
    msg = Message(
        account_id=conv.account_id,
        inbox_id=conv.inbox_id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=CONTENT_TYPE_TEXT,
        content="Hi",
        status=MESSAGE_STATUS_READ,
        sender_type="User",
        sender_id=owner.user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages/{msg.id}",
        json={"status": "delivered"},
        headers=headers,
    )
    assert resp.status_code == 200
    # status didn't actually change
    await db_session.refresh(msg)
    assert msg.status == MESSAGE_STATUS_READ


async def test_messages_update_failed_carries_external_error(
    client, seeded, db_session
):
    owner, _, _, ci, headers = seeded
    conv = await _make_conv(db_session, contact_inbox=ci)
    msg = Message(
        account_id=conv.account_id,
        inbox_id=conv.inbox_id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=CONTENT_TYPE_TEXT,
        content="Hi",
        status=MESSAGE_STATUS_SENT,
        sender_type="User",
        sender_id=owner.user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages/{msg.id}",
        json={"status": "failed", "external_error": "carrier rejected"},
        headers=headers,
    )
    assert resp.status_code == 200
    await db_session.refresh(msg)
    assert (msg.content_attributes or {}).get("external_error") == "carrier rejected"


async def test_messages_update_rejected_for_non_api_inbox(
    client, seeded, db_session
):
    """Mirrors ``ensure_api_inbox`` -> 403 with the Rails error envelope.

    InboxBuilder only ships ``api`` in 4b (other channels arrive Phase
    5b+) so we mutate the seeded API inbox's channel_type directly to
    a non-API value to exercise the guard.
    """

    owner, inbox, _, ci, headers = seeded

    inbox.channel_type = "Channel::WebWidget"
    db_session.add(inbox)
    await db_session.flush()
    # Reload conv so the relationship's ``channel_type`` matches.
    conv = await _make_conv(db_session, contact_inbox=ci)
    await db_session.refresh(conv)

    msg = Message(
        account_id=conv.account_id,
        inbox_id=conv.inbox_id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=CONTENT_TYPE_TEXT,
        content="Hi",
        status=MESSAGE_STATUS_SENT,
        sender_type="User",
        sender_id=owner.user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages/{msg.id}",
        json={"status": "delivered"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json() == {
        "error": "Message status update is only allowed for API inboxes"
    }


async def test_messages_update_unknown_status_returns_422(
    client, seeded, db_session
):
    owner, _, _, ci, headers = seeded
    conv = await _make_conv(db_session, contact_inbox=ci)
    msg = Message(
        account_id=conv.account_id,
        inbox_id=conv.inbox_id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=CONTENT_TYPE_TEXT,
        content="Hi",
        status=MESSAGE_STATUS_SENT,
        sender_type="User",
        sender_id=owner.user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages/{msg.id}",
        json={"status": "frobnicated"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "Invalid message status" in resp.json()["message"]
