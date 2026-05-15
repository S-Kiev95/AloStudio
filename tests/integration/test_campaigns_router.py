"""Integration tests for Campaign CRUD.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/campaigns_controller.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.campaigns.models import (
    CAMPAIGN_STATUS_COMPLETED,
    Campaign,
)
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


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@cmp.example.com",
            account_name=f"CMP{suffix}",
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


async def _seed_inbox(db_session, owner):
    return (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def test_campaigns_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/campaigns")
    assert resp.status_code == 401


async def test_campaigns_create_blocked_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, "-ag")
    agent_owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent-ag@cmp.example.com",
            account_name="Other",
            user_full_name="Agent",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=agent_owner.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=agent_owner.user.tokens, uid=agent_owner.user.uid
    )
    agent_owner.user.tokens = new_tokens
    db_session.add(agent_owner.user)
    await db_session.flush()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/campaigns",
        json={"campaign": {"title": "x", "message": "y"}},
        headers=headers.as_response_headers(),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def test_create_campaign_happy_path(client, db_session):
    owner, headers = await _seed_admin(db_session, "-cr")
    inbox = await _seed_inbox(db_session, owner)
    body = {
        "campaign": {
            "title": "Welcome",
            "message": "Hi there!",
            "inbox_id": inbox.id,
            "trigger_rules": {"url": {"contains": "/pricing"}},
        }
    }
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/campaigns",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["title"] == "Welcome"
    assert payload["display_id"] == 1
    assert payload["campaign_type"] == "ongoing"
    assert payload["campaign_status"] == "active"
    assert payload["enabled"] is True


async def test_display_id_increments_per_account(client, db_session):
    owner, headers = await _seed_admin(db_session, "-di")
    inbox = await _seed_inbox(db_session, owner)
    for i in range(3):
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/campaigns",
            json={
                "campaign": {
                    "title": f"c{i}",
                    "message": "m",
                    "inbox_id": inbox.id,
                }
            },
            headers=headers,
        )
    rows = list(
        (
            await db_session.exec(
                select(Campaign)
                .where(Campaign.account_id == owner.account.id)
                .order_by(Campaign.id.asc())  # type: ignore[attr-defined]
            )
        ).all()
    )
    assert [r.display_id for r in rows] == [1, 2, 3]


async def test_create_rejects_blank_title(client, db_session):
    owner, headers = await _seed_admin(db_session, "-bt")
    inbox = await _seed_inbox(db_session, owner)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/campaigns",
        json={
            "campaign": {
                "title": "",
                "message": "m",
                "inbox_id": inbox.id,
            }
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_rejects_missing_inbox(client, db_session):
    owner, headers = await _seed_admin(db_session, "-mi")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/campaigns",
        json={"campaign": {"title": "x", "message": "y"}},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_rejects_cross_account_inbox(client, db_session):
    owner_a, headers_a = await _seed_admin(db_session, "-ax")
    owner_b, _ = await _seed_admin(db_session, "-bx")
    inbox_b = await _seed_inbox(db_session, owner_b)
    resp = await client.post(
        f"/api/v1/accounts/{owner_a.account.id}/campaigns",
        json={
            "campaign": {
                "title": "x",
                "message": "y",
                "inbox_id": inbox_b.id,
            }
        },
        headers=headers_a,
    )
    assert resp.status_code == 422


async def test_show_by_display_id(client, db_session):
    owner, headers = await _seed_admin(db_session, "-sh")
    inbox = await _seed_inbox(db_session, owner)
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/campaigns",
        json={"campaign": {"title": "X", "message": "Y", "inbox_id": inbox.id}},
        headers=headers,
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/campaigns/1",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "X"


async def test_update_campaign(client, db_session):
    owner, headers = await _seed_admin(db_session, "-up")
    inbox = await _seed_inbox(db_session, owner)
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/campaigns",
        json={"campaign": {"title": "Pre", "message": "M", "inbox_id": inbox.id}},
        headers=headers,
    )
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/campaigns/1",
        json={"campaign": {"title": "Post", "enabled": False}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Post"
    assert resp.json()["enabled"] is False


async def test_update_blocked_when_completed(client, db_session):
    owner, headers = await _seed_admin(db_session, "-co")
    inbox = await _seed_inbox(db_session, owner)
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/campaigns",
        json={"campaign": {"title": "Done", "message": "M", "inbox_id": inbox.id}},
        headers=headers,
    )
    # Force-complete the campaign at the model level (mirrors what
    # the scheduler would do).
    row = (
        await db_session.exec(
            select(Campaign).where(
                Campaign.account_id == owner.account.id,
                Campaign.display_id == 1,
            )
        )
    ).first()
    assert row is not None
    row.campaign_status = CAMPAIGN_STATUS_COMPLETED
    db_session.add(row)
    await db_session.flush()
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/campaigns/1",
        json={"campaign": {"title": "Re-edit"}},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_destroy_campaign(client, db_session):
    owner, headers = await _seed_admin(db_session, "-dl")
    inbox = await _seed_inbox(db_session, owner)
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/campaigns",
        json={"campaign": {"title": "trash", "message": "m", "inbox_id": inbox.id}},
        headers=headers,
    )
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/campaigns/1",
        headers=headers,
    )
    assert resp.status_code == 200
