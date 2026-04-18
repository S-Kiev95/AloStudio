"""HTTP-level tests for ``GET /api/v1/accounts/:id/agents``.

Parity anchor: ``Api::V1::Accounts::AgentsController#index`` →
``index.json.jbuilder`` → ``_agent.json.jbuilder``.

Scope for Phase 1:
  * List returns every user with an AccountUser row in the account.
  * Each entry carries the User fields (id, email, name, ...) plus the
    AccountUser fields for this account (role, availability_status,
    auto_offline).
  * Non-members get 404 (Rails fetch_account behaviour), not 403.
  * Anonymous callers get 401.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_AGENT,
    AccountUser,
)
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


@pytest.fixture
async def account_with_two_users(db_session):
    """Seed: Account with an admin (owner) and a plain agent member."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="owner@rocket.example.com",
            account_name="Rocket Labs",
            user_full_name="Owner Alpha",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    # Second signup (own account) so we have a real User row, then link
    # that user to the owner's account as a plain agent.
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@rocket.example.com",
            account_name="Ignored Second Account",
            user_full_name="Agent Bravo",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    link = AccountUser(
        account_id=owner.account.id,
        user_id=agent.user.id,
        role=ACCOUNT_USER_ROLE_AGENT,
    )
    db_session.add(link)
    await db_session.flush()

    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, agent, headers.as_response_headers()


async def test_agents_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/agents")
    assert resp.status_code == 401


async def test_agents_index_lists_members(client, account_with_two_users):
    owner, agent, headers = account_with_two_users
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/agents", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2

    by_email = {a["email"]: a for a in body}
    assert "owner@rocket.example.com" in by_email
    assert "agent@rocket.example.com" in by_email

    owner_view = by_email["owner@rocket.example.com"]
    assert owner_view["role"] == 1  # administrator
    assert owner_view["account_id"] == owner.account.id
    assert owner_view["availability_status"] == "online"
    assert owner_view["auto_offline"] is True
    assert owner_view["confirmed"] is True
    assert owner_view["available_name"] == "Owner Alpha"

    agent_view = by_email["agent@rocket.example.com"]
    assert agent_view["role"] == 0  # agent


async def test_agents_index_ordered_by_name(client, account_with_two_users):
    owner, _, headers = account_with_two_users
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/agents", headers=headers
    )
    body = resp.json()
    names = [a["name"] for a in body]
    assert names == sorted(names)  # "Agent Bravo" < "Owner Alpha"


async def test_agents_index_404_for_non_member(client, account_with_two_users, db_session):
    _, _, headers = account_with_two_users
    # Account the owner is not part of.
    stranger = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="ghost@rocket.example.com",
            account_name="Ghost Corp",
            user_full_name="Ghost",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    resp = await client.get(
        f"/api/v1/accounts/{stranger.account.id}/agents", headers=headers
    )
    assert resp.status_code == 404
