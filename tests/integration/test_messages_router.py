"""HTTP-level tests for Phase 4a messages nested router.

Routes:
  * ``GET    /api/v1/accounts/:account_id/conversations/:conv_id/messages``
  * ``POST   /api/v1/accounts/:account_id/conversations/:conv_id/messages``
  * ``DELETE /api/v1/accounts/:account_id/conversations/:conv_id/messages/:id``

Parity anchors:
  * ``Api::V1::Accounts::Conversations::MessagesController``
  * ``messages/index.json.jbuilder`` / ``messages/create.json.jbuilder``
  * ``_message.json.jbuilder`` (the slim shape used in create/index responses).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    Attachment,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
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


@pytest.fixture
async def seeded(db_session):
    """Account + admin + API inbox + contact + contact_inbox + conversation."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@msg.example.com",
            account_name="Msg Inc",
            user_full_name="Admin Owner",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent_side = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@msg.example.com",
            account_name="Agent Side",
            user_full_name="Agent Beta",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=agent_side.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()

    inbox_result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API Inbox",
            channel_type="api",
            channel_params={"webhook_url": "https://example.com/hook"},
        ),
    ).perform()

    contact = Contact(
        account_id=owner.account.id,
        email="msg-contact@example.com",
        name="Msg Contact",
    )
    db_session.add(contact)
    await db_session.flush()

    contact_inbox = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox_result.inbox,
    ).perform()

    conv = await create_conversation(
        db_session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(),
    )

    admin_h = await _mint_headers(db_session, owner.user)
    return owner, agent_side, inbox_result.inbox, contact, contact_inbox, conv, admin_h


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def test_messages_index_requires_auth(client, seeded):
    owner, _, _, _, _, conv, _ = seeded
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages"
    )
    assert resp.status_code == 401


async def test_messages_index_unknown_conversation_404(client, seeded):
    owner, _, _, _, _, _, admin_h = seeded
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/9999/messages",
        headers=admin_h,
    )
    assert resp.status_code == 404
    assert resp.json() == {"error": "Resource could not be found"}


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------
async def test_messages_index_empty(client, seeded):
    owner, _, _, _, _, conv, admin_h = seeded
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["payload"] == []
    # meta always ships labels + additional_attributes + contact.
    assert body["meta"]["contact"]["id"] == conv.contact_id
    assert body["meta"]["labels"] == []
    assert body["meta"]["additional_attributes"] == {}


async def test_messages_index_returns_created_messages(client, seeded):
    owner, _, _, _, _, conv, admin_h = seeded
    # Create a message via the endpoint so all callbacks fire.
    for i in range(3):
        r = await client.post(
            f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages",
            json={"content": f"msg {i}", "message_type": "outgoing"},
            headers=admin_h,
        )
        assert r.status_code == 200, r.text

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages",
        headers=admin_h,
    )
    assert resp.status_code == 200
    payload = resp.json()["payload"]
    assert len(payload) == 3
    # Oldest-first in the payload (Rails reverses in the jbuilder).
    assert payload[0]["content"] == "msg 0"
    assert payload[-1]["content"] == "msg 2"


async def test_messages_index_before_cursor(client, seeded, db_session):
    owner, _, _, _, _, conv, admin_h = seeded
    # Seed 3 via the endpoint to pick up real IDs.
    ids = []
    for i in range(3):
        r = await client.post(
            f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages",
            json={"content": f"m{i}", "message_type": "outgoing"},
            headers=admin_h,
        )
        ids.append(r.json()["id"])

    # before=ids[2] → only messages with id < ids[2].
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages"
        f"?before={ids[2]}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    payload = resp.json()["payload"]
    returned_ids = [m["id"] for m in payload]
    assert ids[2] not in returned_ids
    assert ids[0] in returned_ids
    assert ids[1] in returned_ids


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
async def test_create_message_minimal_outgoing(client, seeded):
    owner, _, inbox, _, _, conv, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages",
        json={"content": "hello", "message_type": "outgoing"},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content"] == "hello"
    # Wire message_type is the INTEGER cast (outgoing == 1).
    assert body["message_type"] == 1
    assert body["inbox_id"] == inbox.id
    # display_id of the parent conversation.
    assert body["conversation_id"] == conv.display_id
    # outgoing + authenticated → sender block is the User.
    assert body["sender"]["type"] == "user"


async def test_create_message_incoming_on_api_inbox(client, seeded):
    owner, _, _, contact, _, conv, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages",
        json={"content": "hey there", "message_type": "incoming"},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Wire message_type is the INTEGER cast (incoming == 0).
    assert body["message_type"] == 0
    # Incoming → sender is the contact.
    assert body["sender"]["id"] == contact.id


async def test_create_message_echoes_echo_id(client, seeded):
    owner, _, _, _, _, conv, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages",
        json={
            "content": "echo",
            "message_type": "outgoing",
            "echo_id": "widget-tmp-42",
        },
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["echo_id"] == "widget-tmp-42"


async def test_create_message_attaches_external_url(client, seeded, db_session):
    owner, _, _, _, _, conv, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages",
        json={
            "content": "see pic",
            "message_type": "outgoing",
            "attachments": [
                {
                    "file_type": "image",
                    "external_url": "https://cdn.example.com/a.png",
                    "fallback_title": "a.png",
                }
            ],
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["attachments"]) == 1
    att = body["attachments"][0]
    assert att["data_url"] == "https://cdn.example.com/a.png"
    assert att["file_type"] == "image"


async def test_create_message_rejects_missing_conversation(client, seeded):
    owner, _, _, _, _, _, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/9999/messages",
        json={"content": "hi", "message_type": "outgoing"},
        headers=admin_h,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete (soft-delete)
# ---------------------------------------------------------------------------
async def test_destroy_message_soft_deletes(client, seeded, db_session):
    owner, _, _, _, _, conv, admin_h = seeded
    # Create a message via the endpoint + an attachment so we can prove
    # the attachment is wiped on destroy.
    create_resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages",
        json={
            "content": "please delete",
            "message_type": "outgoing",
            "attachments": [
                {
                    "file_type": "file",
                    "external_url": "https://cdn.example.com/doomed.pdf",
                }
            ],
        },
        headers=admin_h,
    )
    assert create_resp.status_code == 200
    msg_id = create_resp.json()["id"]

    # Sanity: attachment row exists pre-delete.
    pre_att = (
        await db_session.exec(select(Attachment).where(Attachment.message_id == msg_id))
    ).all()
    assert len(pre_att) == 1

    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages/{msg_id}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    # Soft-delete: content replaced, content_attributes[deleted]=True.
    assert body["content"] == "This message was deleted"
    assert body["content_attributes"]["deleted"] is True

    # Row still exists (soft delete — the Message stays).
    still_there = await db_session.get(Message, msg_id)
    assert still_there is not None
    # Attachments wiped.
    post_att = (
        await db_session.exec(select(Attachment).where(Attachment.message_id == msg_id))
    ).all()
    assert post_att == []


async def test_destroy_unknown_message_404(client, seeded):
    owner, _, _, _, _, conv, admin_h = seeded
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/messages/987654",
        headers=admin_h,
    )
    assert resp.status_code == 404
    assert resp.json() == {"error": "Resource could not be found"}
