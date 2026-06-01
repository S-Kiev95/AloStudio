"""Integration tests for the agent admin endpoints.

Anchors:
  app/domains/accounts/router.py (POST/PATCH/DELETE /agents)
  app/domains/agents/service.py
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    ACCOUNT_USER_ROLE_AGENT,
    AccountUser,
    User,
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
def stub_invitation_mail():
    """Stub the SMTP send so tests don't hit MailHog (and stay deterministic)."""
    with patch(
        "app.domains.agents.service.aiosmtplib.send",
        new_callable=AsyncMock,
    ) as send:
        yield send


async def _seed_admin(db_session, suffix: str = ""):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@agents.example.com",
            account_name=f"Agents{suffix}",
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


async def _seed_agent(db_session, suffix: str = ""):
    """Account with a non-admin agent — for permission tests."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@agents.example.com",
            account_name=f"AgentsA{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
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
# Invite happy path
# ---------------------------------------------------------------------------
async def test_invite_creates_user_account_user_and_token(
    client, db_session, stub_invitation_mail
):
    owner, headers = await _seed_admin(db_session)
    aid = owner.account.id

    res = await client.post(
        f"/api/v1/accounts/{aid}/agents",
        headers=headers,
        json={
            "agent": {
                "email": "newbie@example.com",
                "name": "Newbie",
                "role": "agent",
            }
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email"] == "newbie@example.com"
    assert body["name"] == "Newbie"
    assert body["role"] == ACCOUNT_USER_ROLE_AGENT
    # ``confirmed`` is true because the invite skips Devise's
    # confirmation step (admin vouched). The reset_password flow sets
    # the password.
    assert body["confirmed"] is True

    # A User row exists with a reset_password_token.
    user = (
        await db_session.exec(
            select(User).where(User.email == "newbie@example.com")
        )
    ).first()
    assert user is not None
    assert user.reset_password_token is not None
    assert user.reset_password_sent_at is not None

    # An AccountUser row exists, with the inviter recorded.
    au = (
        await db_session.exec(
            select(AccountUser).where(
                AccountUser.account_id == aid, AccountUser.user_id == user.id
            )
        )
    ).first()
    assert au is not None
    assert au.role == ACCOUNT_USER_ROLE_AGENT
    assert au.inviter_id == owner.user.id

    # Email send was attempted exactly once.
    assert stub_invitation_mail.await_count == 1


async def test_invite_administrator_role(client, db_session, stub_invitation_mail):
    owner, headers = await _seed_admin(db_session, "-r")
    aid = owner.account.id

    res = await client.post(
        f"/api/v1/accounts/{aid}/agents",
        headers=headers,
        json={
            "agent": {
                "email": "admin2@example.com",
                "name": "Admin Dos",
                "role": "administrator",
            }
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["role"] == ACCOUNT_USER_ROLE_ADMINISTRATOR


# ---------------------------------------------------------------------------
# Invite — duplicate email rejected (422)
# ---------------------------------------------------------------------------
async def test_invite_dup_returns_422(client, db_session, stub_invitation_mail):
    owner, headers = await _seed_admin(db_session, "-d")
    aid = owner.account.id

    payload = {"agent": {"email": "dup@example.com", "name": "Dup"}}
    first = await client.post(
        f"/api/v1/accounts/{aid}/agents", headers=headers, json=payload
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/accounts/{aid}/agents", headers=headers, json=payload
    )
    assert second.status_code == 422
    assert "already" in second.json()["message"].lower()


# ---------------------------------------------------------------------------
# Update role
# ---------------------------------------------------------------------------
async def test_update_role_promotes_agent_to_admin(
    client, db_session, stub_invitation_mail
):
    owner, headers = await _seed_admin(db_session, "-u")
    aid = owner.account.id

    invited = (
        await client.post(
            f"/api/v1/accounts/{aid}/agents",
            headers=headers,
            json={"agent": {"email": "promote@example.com", "name": "Promo"}},
        )
    ).json()

    res = await client.patch(
        f"/api/v1/accounts/{aid}/agents/{invited['id']}",
        headers=headers,
        json={"agent": {"role": "administrator", "name": "Promo Updated"}},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["role"] == ACCOUNT_USER_ROLE_ADMINISTRATOR
    assert body["name"] == "Promo Updated"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
async def test_delete_removes_account_user_but_keeps_user(
    client, db_session, stub_invitation_mail
):
    owner, headers = await _seed_admin(db_session, "-rm")
    aid = owner.account.id

    invited = (
        await client.post(
            f"/api/v1/accounts/{aid}/agents",
            headers=headers,
            json={"agent": {"email": "bye@example.com", "name": "Bye"}},
        )
    ).json()

    res = await client.delete(
        f"/api/v1/accounts/{aid}/agents/{invited['id']}", headers=headers
    )
    assert res.status_code == 200
    assert res.json() == {}

    # AccountUser row gone.
    au = (
        await db_session.exec(
            select(AccountUser).where(
                AccountUser.account_id == aid, AccountUser.user_id == invited["id"]
            )
        )
    ).first()
    assert au is None
    # User row stays.
    user = await db_session.get(User, invited["id"])
    assert user is not None
    assert user.email == "bye@example.com"


# ---------------------------------------------------------------------------
# Admin gate
# ---------------------------------------------------------------------------
async def test_agent_cannot_invite(client, db_session, stub_invitation_mail):
    owner, headers = await _seed_agent(db_session, "-ag")
    aid = owner.account.id

    res = await client.post(
        f"/api/v1/accounts/{aid}/agents",
        headers=headers,
        json={"agent": {"email": "blocked@example.com", "name": "Blocked"}},
    )
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
async def test_invite_bad_email_422(client, db_session, stub_invitation_mail):
    owner, headers = await _seed_admin(db_session, "-bad")
    aid = owner.account.id

    res = await client.post(
        f"/api/v1/accounts/{aid}/agents",
        headers=headers,
        json={"agent": {"email": "not-an-email", "name": "X"}},
    )
    assert res.status_code == 422
