"""Integration tests for the Integration hooks + apps surface.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/integrations/apps_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/integrations/hooks_controller.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
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


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@int.example.com",
            account_name=f"Int{suffix}",
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
            email=f"agent{suffix}@int.example.com",
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


# ---------------------------------------------------------------------------
# Apps catalogue
# ---------------------------------------------------------------------------
async def test_apps_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/integrations/apps")
    assert resp.status_code == 401


async def test_apps_index_returns_catalogue_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, "-ag")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, "-ag"
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/integrations/apps",
        headers=agent_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "payload" in body
    ids = {app["id"] for app in body["payload"]}
    # Catalogue includes Slack/Dialogflow/etc.
    assert "slack" in ids
    assert "dialogflow" in ids
    assert "openai" in ids
    # Agents don't see ``settings`` / ``allow_multiple_hooks``.
    assert "settings" not in body["payload"][0]
    assert "allow_multiple_hooks" not in body["payload"][0]


async def test_apps_show_404_unknown_id(client, db_session):
    owner, headers = await _seed_admin(db_session, "-na")
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/integrations/apps/frobnicate",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_apps_expose_connect_action_and_hook_type(client, db_session):
    """Each app carries the Connect metadata the dashboard drives off."""
    owner, headers = await _seed_admin(db_session, "-act")
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/integrations/apps",
        headers=headers,
    )
    assert resp.status_code == 200
    by_id = {app["id"]: app for app in resp.json()["payload"]}
    # Inline app → relative action + inbox hook_type.
    assert by_id["dialogflow"]["action"] == "/dialogflow"
    assert by_id["dialogflow"]["hook_type"] == "inbox"
    assert by_id["webhook"]["action"] == "/webhook"
    assert by_id["webhook"]["hook_type"] == "account"
    # OAuth app with no client id configured → not connectable (null action).
    assert by_id["slack"]["action"] is None
    assert by_id["slack"]["hook_type"] == "account"
    # An app with no action stays null.
    assert by_id["shopify"]["action"] is None


async def test_apps_index_includes_account_hooks(client, db_session):
    owner, headers = await _seed_admin(db_session, "-hk")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={"hook": {"app_id": "slack", "settings": {"channel": "#cs"}}},
        headers=headers,
    )
    assert create.status_code == 200
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/integrations/apps",
        headers=headers,
    )
    body = resp.json()["payload"]
    slack_entry = next(app for app in body if app["id"] == "slack")
    assert len(slack_entry["hooks"]) == 1
    assert slack_entry["hooks"][0]["app_id"] == "slack"


# ---------------------------------------------------------------------------
# Hook CRUD
# ---------------------------------------------------------------------------
async def test_hook_create_requires_admin(client, db_session):
    owner, _ = await _seed_admin(db_session, "-cr")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, "-cr"
    )
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={"hook": {"app_id": "slack"}},
        headers=agent_headers,
    )
    assert resp.status_code == 401


async def test_hook_create_happy_path(client, db_session):
    owner, headers = await _seed_admin(db_session, "-cs")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={
            "hook": {
                "app_id": "dialogflow",
                "settings": {"project_id": "my-project"},
            }
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["app_id"] == "dialogflow"
    assert body["status"] is True
    assert body["account_id"] == owner.account.id
    assert body["hook_type"] == "account"
    assert body["settings"] == {"project_id": "my-project"}


async def test_hook_create_rejects_unknown_app(client, db_session):
    owner, headers = await _seed_admin(db_session, "-un")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={"hook": {"app_id": "frobnicate"}},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_hook_uniqueness_per_account(client, db_session):
    """Single-instance apps (e.g. Slack) can't have two hooks per
    account."""
    owner, headers = await _seed_admin(db_session, "-dup")
    r1 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={"hook": {"app_id": "slack"}},
        headers=headers,
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={"hook": {"app_id": "slack"}},
        headers=headers,
    )
    assert r2.status_code == 422


async def test_hook_allow_multiple_for_webhook_app(client, db_session):
    """The ``webhook`` app advertises ``allow_multiple_hooks`` —
    two hooks for the same account succeed."""
    owner, headers = await _seed_admin(db_session, "-mh")
    r1 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={"hook": {"app_id": "webhook"}},
        headers=headers,
    )
    r2 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={"hook": {"app_id": "webhook"}},
        headers=headers,
    )
    assert r1.status_code == 200
    assert r2.status_code == 200


async def test_hook_update_toggles_status(client, db_session):
    owner, headers = await _seed_admin(db_session, "-up")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={"hook": {"app_id": "linear"}},
        headers=headers,
    )
    hid = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks/{hid}",
        json={"hook": {"status": False}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] is False


async def test_hook_destroy_returns_200(client, db_session):
    owner, headers = await _seed_admin(db_session, "-dl")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks",
        json={"hook": {"app_id": "shopify"}},
        headers=headers,
    )
    hid = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks/{hid}",
        headers=headers,
    )
    assert resp.status_code == 200


async def test_hook_unknown_id_returns_404(client, db_session):
    owner, headers = await _seed_admin(db_session, "-nf")
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/integrations/hooks/9999",
        json={"hook": {"status": True}},
        headers=headers,
    )
    assert resp.status_code == 404
