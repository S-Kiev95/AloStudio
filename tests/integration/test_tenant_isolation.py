"""Tenant isolation: an account must not reach another account's data.

F2 (multitenant). Account A is the one making the requests; account B holds
the foreign user, team and Help Center that A tries to reference by id.
Each finding of the audit in ``PLAN.multitenant.md`` gets its case here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.portals.models import Portal
from app.domains.teams.models import Team
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


async def _account(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@tenant.example.com",
            account_name=f"Tenant{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _api_inbox(db_session, owner):
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={},
            enable_auto_assignment=False,
        ),
    ).perform()
    return result.inbox


async def _team(db_session, owner, name: str) -> Team:
    team = Team(account_id=owner.account.id, name=name)
    db_session.add(team)
    await db_session.flush()
    return team


@pytest.fixture
async def two_accounts(db_session):
    a, headers = await _account(db_session, "-a")
    b, _ = await _account(db_session, "-b")
    return a, headers, b


async def test_inbox_members_refuse_a_user_of_another_account(client, db_session, two_accounts):
    a, headers, b = two_accounts
    inbox = await _api_inbox(db_session, a)
    res = await client.post(
        f"/api/v1/accounts/{a.account.id}/inbox_members",
        headers=headers,
        json={"inbox_id": inbox.id, "user_ids": [b.user.id]},
    )
    assert res.status_code == 422
    # Nothing about B's user leaks back.
    assert b.user.email not in res.text

    # A's own user is still fine.
    res = await client.post(
        f"/api/v1/accounts/{a.account.id}/inbox_members",
        headers=headers,
        json={"inbox_id": inbox.id, "user_ids": [a.user.id]},
    )
    assert res.status_code == 200, res.text


async def test_team_members_refuse_a_user_of_another_account(client, db_session, two_accounts):
    a, headers, b = two_accounts
    team = await _team(db_session, a, "Ventas")
    res = await client.post(
        f"/api/v1/accounts/{a.account.id}/teams/{team.id}/team_members",
        headers=headers,
        json={"user_ids": [b.user.id]},
    )
    # Chatwoot's ``validate_member_id_params`` answers 401 "Invalid User IDs".
    assert res.status_code == 401
    assert b.user.email not in res.text


async def test_new_conversation_refuses_foreign_assignee_and_team(client, db_session, two_accounts):
    a, headers, b = two_accounts
    inbox = await _api_inbox(db_session, a)
    contact = Contact(account_id=a.account.id, name="Cliente A")
    db_session.add(contact)
    await db_session.flush()
    foreign_team = await _team(db_session, b, "Soporte B")
    url = f"/api/v1/accounts/{a.account.id}/conversations"
    base = {"inbox_id": inbox.id, "contact_id": contact.id}

    res = await client.post(url, headers=headers, json={**base, "assignee_id": b.user.id})
    assert res.status_code == 422

    res = await client.post(url, headers=headers, json={**base, "team_id": foreign_team.id})
    assert res.status_code == 422

    res = await client.post(url, headers=headers, json={**base, "assignee_id": a.user.id})
    assert res.status_code == 200, res.text


async def test_inbox_refuses_the_help_center_of_another_account(client, db_session, two_accounts):
    a, headers, b = two_accounts
    inbox = await _api_inbox(db_session, a)
    foreign_portal = Portal(account_id=b.account.id, name="Ayuda B", slug="ayuda-b")
    db_session.add(foreign_portal)
    await db_session.flush()

    res = await client.patch(
        f"/api/v1/accounts/{a.account.id}/inboxes/{inbox.id}",
        headers=headers,
        json={"portal_id": foreign_portal.id},
    )
    assert res.status_code == 422
    await db_session.refresh(inbox)
    assert inbox.portal_id is None
