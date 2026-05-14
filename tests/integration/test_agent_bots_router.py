"""Integration tests for AgentBot CRUD + AgentBotInbox attach/detach.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/agent_bots_controller.rb
  reference/chatwoot/app/policies/agent_bot_policy.rb
  reference/chatwoot/app/controllers/api/v1/accounts/inboxes_controller.rb
    (set_agent_bot member action)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.agent_bots.models import AgentBot, AgentBotInbox
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
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


async def _seed_admin(db_session, suffix: str = ""):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@bots.example.com",
            account_name=f"Bots{suffix}",
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


async def _seed_agent_member(db_session, owner_account, suffix: str):
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@bots.example.com",
            account_name=f"Other{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner_account.id,
            user_id=agent.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=agent.user.tokens, uid=agent.user.uid
    )
    agent.user.tokens = new_tokens
    db_session.add(agent.user)
    await db_session.flush()
    return agent, headers.as_response_headers()


async def _seed_inbox(db_session, owner):
    res = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    return res.inbox


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------
async def test_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/agent_bots")
    assert resp.status_code == 401


async def test_create_blocked_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, "-ca")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, "-ca"
    )
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/agent_bots",
        json={"name": "bot"},
        headers=agent_headers,
    )
    assert resp.status_code == 401


async def test_index_works_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, "-ai")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, "-ai"
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/agent_bots",
        headers=agent_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# CRUD happy paths
# ---------------------------------------------------------------------------
async def test_create_returns_bot_with_secret(client, db_session):
    owner, headers = await _seed_admin(db_session, "-cr")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/agent_bots",
        json={
            "name": "Triage Bot",
            "description": "First-line",
            "outgoing_url": "https://bot.example.com/hook",
            "bot_config": {"locale": "en"},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Triage Bot"
    assert body["description"] == "First-line"
    assert body["outgoing_url"] == "https://bot.example.com/hook"
    assert body["bot_type"] == "webhook"
    assert body["bot_config"] == {"locale": "en"}
    assert body["account_id"] == owner.account.id
    assert body["system_bot"] is False
    # Secret revealed to admins on create.
    assert isinstance(body["secret"], str)
    assert len(body["secret"]) == 24  # secrets.token_hex(12)


async def test_create_rejects_blank_name(client, db_session):
    owner, headers = await _seed_admin(db_session, "-bn")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/agent_bots",
        json={"name": ""},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_update_changes_outgoing_url(client, db_session):
    owner, headers = await _seed_admin(db_session, "-up")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/agent_bots",
        json={"name": "Bot", "outgoing_url": "https://a.example.com"},
        headers=headers,
    )
    bid = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/agent_bots/{bid}",
        json={"outgoing_url": "https://b.example.com"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["outgoing_url"] == "https://b.example.com"


async def test_destroy_returns_200_empty(client, db_session):
    owner, headers = await _seed_admin(db_session, "-dl")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/agent_bots",
        json={"name": "trash"},
        headers=headers,
    )
    bid = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/agent_bots/{bid}",
        headers=headers,
    )
    assert resp.status_code == 200


async def test_reset_secret_rotates_value(client, db_session):
    owner, headers = await _seed_admin(db_session, "-rs")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/agent_bots",
        json={"name": "bot"},
        headers=headers,
    )
    bid = create.json()["id"]
    old_secret = create.json()["secret"]
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/agent_bots/{bid}/reset_secret",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["secret"] != old_secret


async def test_other_account_bot_returns_404(client, db_session):
    """A bot owned by another account is invisible to the caller."""
    owner_a, headers_a = await _seed_admin(db_session, "-ax")
    owner_b, _ = await _seed_admin(db_session, "-bx")
    bot = AgentBot(account_id=owner_b.account.id, name="b-bot")
    db_session.add(bot)
    await db_session.flush()
    await db_session.refresh(bot)
    resp = await client.get(
        f"/api/v1/accounts/{owner_a.account.id}/agent_bots/{bot.id}",
        headers=headers_a,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AgentBotInbox attach / detach
# ---------------------------------------------------------------------------
async def test_set_agent_bot_attaches(client, db_session):
    owner, headers = await _seed_admin(db_session, "-at")
    inbox = await _seed_inbox(db_session, owner)
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/agent_bots",
        json={"name": "bot"},
        headers=headers,
    )
    bid = create.json()["id"]
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/set_agent_bot",
        json={"agent_bot": bid},
        headers=headers,
    )
    assert resp.status_code == 200
    join = (
        await db_session.exec(
            select(AgentBotInbox).where(
                AgentBotInbox.inbox_id == inbox.id
            )
        )
    ).first()
    assert join is not None
    assert join.agent_bot_id == bid


async def test_set_agent_bot_null_detaches(client, db_session):
    owner, headers = await _seed_admin(db_session, "-de")
    inbox = await _seed_inbox(db_session, owner)
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/agent_bots",
        json={"name": "bot"},
        headers=headers,
    )
    bid = create.json()["id"]
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/set_agent_bot",
        json={"agent_bot": bid},
        headers=headers,
    )
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/set_agent_bot",
        json={"agent_bot": None},
        headers=headers,
    )
    assert resp.status_code == 200
    join = (
        await db_session.exec(
            select(AgentBotInbox).where(
                AgentBotInbox.inbox_id == inbox.id
            )
        )
    ).first()
    assert join is None


async def test_set_agent_bot_replaces_existing(client, db_session):
    """Only one bot per inbox — attaching a second drops the first."""
    owner, headers = await _seed_admin(db_session, "-rp")
    inbox = await _seed_inbox(db_session, owner)
    b1 = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/agent_bots",
            json={"name": "first"},
            headers=headers,
        )
    ).json()["id"]
    b2 = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/agent_bots",
            json={"name": "second"},
            headers=headers,
        )
    ).json()["id"]
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/set_agent_bot",
        json={"agent_bot": b1},
        headers=headers,
    )
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/set_agent_bot",
        json={"agent_bot": b2},
        headers=headers,
    )
    joins = list(
        (
            await db_session.exec(
                select(AgentBotInbox).where(
                    AgentBotInbox.inbox_id == inbox.id
                )
            )
        ).all()
    )
    assert len(joins) == 1
    assert joins[0].agent_bot_id == b2


async def test_set_agent_bot_blocked_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, "-au")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, "-au"
    )
    inbox = await _seed_inbox(db_session, owner)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/set_agent_bot",
        json={"agent_bot": 999},
        headers=agent_headers,
    )
    assert resp.status_code == 401
