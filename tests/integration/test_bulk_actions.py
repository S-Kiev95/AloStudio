"""Integration tests for ``POST /api/v1/accounts/:id/bulk_actions``.

Anchor: ``Api::V1::Accounts::BulkActionsController`` (Conversation slice).
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
    CONVERSATION_STATUS_RESOLVED,
    Conversation,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
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
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@bulk.example.com",
            account_name="Bulk Inc",
            user_full_name="Admin Bulk",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://b.example.com/h"},
            ),
        ).perform()
    ).inbox
    contact = Contact(
        account_id=owner.account.id,
        email="c@bulk.example.com",
        name="Bulk Contact",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox
    ).perform()
    admin_h = await _mint_headers(db_session, owner.user)
    return owner, ci, admin_h


async def _make_conv(db_session, *, contact_inbox) -> Conversation:
    # Load contact_inbox.inbox in async context first — create_conversation
    # reads it (service.py:190) and a lazy load there trips MissingGreenlet.
    await db_session.refresh(contact_inbox, ["inbox"])
    return await create_conversation(
        db_session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(),
    )


async def test_bulk_resolve_conversations(client, seeded, db_session):
    owner, ci, admin_h = seeded
    c1 = await _make_conv(db_session, contact_inbox=ci)
    c2 = await _make_conv(db_session, contact_inbox=ci)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/bulk_actions",
        json={
            "type": "Conversation",
            "ids": [c1.display_id, c2.display_id],
            "fields": {"status": "resolved"},
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["payload"]["updated"]) == {
        c1.display_id,
        c2.display_id,
    }

    await db_session.refresh(c1)
    await db_session.refresh(c2)
    assert c1.status == CONVERSATION_STATUS_RESOLVED
    assert c2.status == CONVERSATION_STATUS_RESOLVED


async def test_bulk_assign_conversations(client, seeded, db_session):
    owner, ci, admin_h = seeded
    c1 = await _make_conv(db_session, contact_inbox=ci)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/bulk_actions",
        json={
            "type": "Conversation",
            "ids": [c1.display_id],
            "fields": {"assignee_id": owner.user.id},
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    await db_session.refresh(c1)
    assert c1.assignee_id == owner.user.id


async def test_bulk_ignores_out_of_account_ids(client, seeded, db_session):
    owner, ci, admin_h = seeded
    c1 = await _make_conv(db_session, contact_inbox=ci)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/bulk_actions",
        json={
            "type": "Conversation",
            "ids": [c1.display_id, 999999],
            "fields": {"status": "resolved"},
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    # Only the real conversation is touched; the bogus id is skipped.
    assert resp.json()["payload"]["updated"] == [c1.display_id]
