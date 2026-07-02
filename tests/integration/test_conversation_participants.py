"""Integration tests for the conversation participants surface.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/conversations/participants_controller.rb
  reference/chatwoot/app/models/conversation_participant.rb

Coverage:
  * show → the watcher list (array of agent partials).
  * create → adds user_ids; only *assignable agents* (inbox member or
    account admin) may be added, else 422.
  * update → reconciles the set (adds missing, removes extra).
  * destroy → removes the given user_ids (``head :ok``).
  * idempotency — re-adding an existing participant is a no-op.
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
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration


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
    """Owner (admin) + agent_a (inbox member) + agent_b (no membership),
    one API inbox with one conversation. Returns the pieces the tests
    address the endpoints with."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@part.example.com",
            account_name="Part Inc",
            user_full_name="Admin Part",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent_a = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent_a@part.example.com",
            account_name="A Side",
            user_full_name="Agent A",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent_b = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent_b@part.example.com",
            account_name="B Side",
            user_full_name="Agent B",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add_all(
        [
            AccountUser(
                account_id=owner.account.id,
                user_id=agent_a.user.id,
                role=ACCOUNT_USER_ROLE_AGENT,
            ),
            AccountUser(
                account_id=owner.account.id,
                user_id=agent_b.user.id,
                role=ACCOUNT_USER_ROLE_AGENT,
            ),
        ]
    )
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Inbox",
                channel_type="api",
                channel_params={"webhook_url": "https://i.example.com/h"},
            ),
        ).perform()
    ).inbox
    # agent_a is a member of the inbox; agent_b is not.
    db_session.add(InboxMember(inbox_id=inbox.id, user_id=agent_a.user.id))

    contact = Contact(
        account_id=owner.account.id,
        email="c@part.example.com",
        name="Part Contact",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox
    ).perform()
    conv = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )
    admin_h = await _mint_headers(db_session, owner.user)
    return owner, agent_a, agent_b, conv, admin_h


def _url(account_id: int, display_id: int) -> str:
    return (
        f"/api/v1/accounts/{account_id}/conversations/{display_id}/participants"
    )


async def test_show_starts_empty(client, seeded):
    owner, _, _, conv, admin_h = seeded
    resp = await client.get(_url(owner.account.id, conv.display_id), headers=admin_h)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_add_inbox_member_and_show(client, seeded):
    owner, agent_a, _, conv, admin_h = seeded
    url = _url(owner.account.id, conv.display_id)
    resp = await client.post(
        url, json={"user_ids": [agent_a.user.id]}, headers=admin_h
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [p["id"] for p in body] == [agent_a.user.id]
    # A subsequent show returns the same watcher.
    shown = (await client.get(url, headers=admin_h)).json()
    assert [p["id"] for p in shown] == [agent_a.user.id]


async def test_admin_is_assignable(client, seeded):
    """The account admin counts as an assignable agent of every inbox."""
    owner, _, _, conv, admin_h = seeded
    resp = await client.post(
        _url(owner.account.id, conv.display_id),
        json={"user_ids": [owner.user.id]},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    assert [p["id"] for p in resp.json()] == [owner.user.id]


async def test_non_assignable_user_is_rejected(client, seeded):
    """agent_b is neither an inbox member nor an admin → 422."""
    owner, _, agent_b, conv, admin_h = seeded
    resp = await client.post(
        _url(owner.account.id, conv.display_id),
        json={"user_ids": [agent_b.user.id]},
        headers=admin_h,
    )
    assert resp.status_code == 422, resp.text
    assert "inbox access" in resp.json()["message"].lower()
    # Nothing was persisted.
    assert (await client.get(_url(owner.account.id, conv.display_id), headers=admin_h)).json() == []


async def test_adding_twice_is_idempotent(client, seeded):
    owner, agent_a, _, conv, admin_h = seeded
    url = _url(owner.account.id, conv.display_id)
    await client.post(url, json={"user_ids": [agent_a.user.id]}, headers=admin_h)
    again = await client.post(
        url, json={"user_ids": [agent_a.user.id]}, headers=admin_h
    )
    assert again.status_code == 200
    assert [p["id"] for p in again.json()] == [agent_a.user.id]


async def test_update_reconciles_the_set(client, seeded):
    owner, agent_a, _, conv, admin_h = seeded
    url = _url(owner.account.id, conv.display_id)
    await client.post(url, json={"user_ids": [agent_a.user.id]}, headers=admin_h)
    # Reconcile to just the admin → agent_a removed, admin added.
    resp = await client.patch(
        url, json={"user_ids": [owner.user.id]}, headers=admin_h
    )
    assert resp.status_code == 200, resp.text
    assert [p["id"] for p in resp.json()] == [owner.user.id]


async def test_destroy_removes_named_users(client, seeded):
    owner, agent_a, _, conv, admin_h = seeded
    url = _url(owner.account.id, conv.display_id)
    await client.post(
        url,
        json={"user_ids": [agent_a.user.id, owner.user.id]},
        headers=admin_h,
    )
    dele = await client.request(
        "DELETE", url, json={"user_ids": [agent_a.user.id]}, headers=admin_h
    )
    assert dele.status_code == 200
    assert dele.json() == {}
    remaining = (await client.get(url, headers=admin_h)).json()
    assert [p["id"] for p in remaining] == [owner.user.id]
