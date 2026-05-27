"""Integration tests for the MCP token admin CRUD surface.

Anchors:
  app/mcp/router.py
  app/mcp/service.py
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app
from app.mcp.models import MCPToken

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


async def _seed_admin(db_session, suffix: str = ""):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcp.example.com",
            account_name=f"Mcp{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _seed_agent(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@mcp.example.com",
            account_name="McpAgent",
            user_full_name="Agent",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    # Demote the AccountUser from administrator to agent.
    au = (
        await db_session.exec(
            select(AccountUser).where(
                AccountUser.account_id == owner.account.id,
                AccountUser.user_id == owner.user.id,
            )
        )
    ).first()
    assert au is not None
    au.role = ACCOUNT_USER_ROLE_AGENT
    db_session.add(au)
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


# ---------------------------------------------------------------------------
# Index + create + secret reveal
# ---------------------------------------------------------------------------
async def test_index_starts_empty_then_create_reveals_secret_once(
    client, db_session
):
    owner, headers = await _seed_admin(db_session)
    aid = owner.account.id

    # Index — empty
    res = await client.get(
        f"/api/v1/accounts/{aid}/mcp_tokens", headers=headers
    )
    assert res.status_code == 200
    assert res.json() == {"payload": []}

    # Create with explicit scope
    res = await client.post(
        f"/api/v1/accounts/{aid}/mcp_tokens",
        headers=headers,
        json={"name": "agent-1", "scope": "write"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "agent-1"
    assert body["scope"] == "write"
    assert body["token"] and len(body["token"]) >= 32
    secret = body["token"]
    token_id = body["id"]

    # Index now contains it BUT no secret.
    res = await client.get(
        f"/api/v1/accounts/{aid}/mcp_tokens", headers=headers
    )
    assert res.status_code == 200
    payload = res.json()["payload"]
    assert len(payload) == 1
    assert payload[0]["name"] == "agent-1"
    assert "token" not in payload[0]

    # The row in the DB carries the same secret as the create response.
    row = (
        await db_session.exec(
            select(MCPToken).where(MCPToken.id == token_id)
        )
    ).first()
    assert row is not None
    assert row.token == secret


# ---------------------------------------------------------------------------
# Rename / re-scope
# ---------------------------------------------------------------------------
async def test_update_renames_and_rescopes_without_rotating_secret(
    client, db_session
):
    owner, headers = await _seed_admin(db_session, "u")
    aid = owner.account.id
    res = await client.post(
        f"/api/v1/accounts/{aid}/mcp_tokens",
        headers=headers,
        json={"name": "old", "scope": "read"},
    )
    token_id = res.json()["id"]
    original_secret = res.json()["token"]

    res = await client.patch(
        f"/api/v1/accounts/{aid}/mcp_tokens/{token_id}",
        headers=headers,
        json={"name": "renamed", "scope": "admin"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "renamed"
    assert body["scope"] == "admin"
    # Secret is NOT included on update.
    assert "token" not in body

    # …and the underlying secret didn't change.
    row = (
        await db_session.exec(
            select(MCPToken).where(MCPToken.id == token_id)
        )
    ).first()
    assert row is not None
    assert row.token == original_secret


# ---------------------------------------------------------------------------
# Rotate
# ---------------------------------------------------------------------------
async def test_rotate_returns_a_new_secret(client, db_session):
    owner, headers = await _seed_admin(db_session, "r")
    aid = owner.account.id
    res = await client.post(
        f"/api/v1/accounts/{aid}/mcp_tokens",
        headers=headers,
        json={"name": "rotateme"},
    )
    token_id = res.json()["id"]
    original = res.json()["token"]

    res = await client.post(
        f"/api/v1/accounts/{aid}/mcp_tokens/{token_id}/rotate",
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token"] and body["token"] != original


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
async def test_delete_removes_the_row(client, db_session):
    owner, headers = await _seed_admin(db_session, "d")
    aid = owner.account.id
    res = await client.post(
        f"/api/v1/accounts/{aid}/mcp_tokens",
        headers=headers,
        json={"name": "kill-me"},
    )
    token_id = res.json()["id"]

    res = await client.delete(
        f"/api/v1/accounts/{aid}/mcp_tokens/{token_id}", headers=headers
    )
    assert res.status_code == 200
    assert res.json() == {}

    row = (
        await db_session.exec(
            select(MCPToken).where(MCPToken.id == token_id)
        )
    ).first()
    assert row is None


# ---------------------------------------------------------------------------
# Admin gate
# ---------------------------------------------------------------------------
async def test_agent_cannot_list_or_create(client, db_session):
    owner, headers = await _seed_agent(db_session)
    aid = owner.account.id

    res = await client.get(
        f"/api/v1/accounts/{aid}/mcp_tokens", headers=headers
    )
    assert res.status_code in (401, 403)

    res = await client.post(
        f"/api/v1/accounts/{aid}/mcp_tokens",
        headers=headers,
        json={"name": "nope"},
    )
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
async def test_invalid_scope_is_rejected(client, db_session):
    owner, headers = await _seed_admin(db_session, "v")
    aid = owner.account.id
    res = await client.post(
        f"/api/v1/accounts/{aid}/mcp_tokens",
        headers=headers,
        json={"name": "bad", "scope": "godmode"},
    )
    assert res.status_code == 422
