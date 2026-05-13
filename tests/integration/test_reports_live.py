"""Integration tests for the live reports endpoints.

Anchors:
  reference/chatwoot/app/controllers/api/v2/accounts/live_reports_controller.rb
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
    toggle_status,
    update_assignee,
    update_team,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams.models import Team
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
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
            email=f"admin{suffix}@live.example.com",
            account_name=f"Live{suffix}",
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


async def _seed_conversation(db_session, owner):
    inbox = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox.inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    return await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------
async def test_live_conversation_metrics_requires_auth(client):
    resp = await client.get(
        "/api/v2/accounts/1/live_reports/conversation_metrics"
    )
    assert resp.status_code == 401


async def test_grouped_conversation_metrics_requires_auth(client):
    resp = await client.get(
        "/api/v2/accounts/1/live_reports/grouped_conversation_metrics?group_by=team_id"
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# conversation_metrics
# ---------------------------------------------------------------------------
async def test_live_counters_empty(client, db_session):
    owner, headers = await _seed_admin(db_session, "-em")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/live_reports/conversation_metrics",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "open": 0,
        "unattended": 0,
        "unassigned": 0,
        "pending": 0,
    }


async def test_live_counters_reflect_seeded_conversations(client, db_session):
    owner, headers = await _seed_admin(db_session, "-cnt")
    # 2 open, 1 resolved.
    await _seed_conversation(db_session, owner)
    await _seed_conversation(db_session, owner)
    resolved = await _seed_conversation(db_session, owner)
    await toggle_status(
        db_session, conversation=resolved, status="resolved"
    )
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/live_reports/conversation_metrics",
        headers=headers,
    )
    body = resp.json()
    assert body["open"] == 2
    assert body["unattended"] == 2
    assert body["unassigned"] == 2


# ---------------------------------------------------------------------------
# grouped_conversation_metrics
# ---------------------------------------------------------------------------
async def test_grouped_requires_valid_group_by(client, db_session):
    owner, headers = await _seed_admin(db_session, "-gv")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/live_reports/grouped_conversation_metrics?group_by=label",
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json() == {"error": "invalid group_by"}


async def test_grouped_by_assignee(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ga")
    # Two convs assigned to the owner, one unassigned.
    c1 = await _seed_conversation(db_session, owner)
    c2 = await _seed_conversation(db_session, owner)
    await _seed_conversation(db_session, owner)
    await update_assignee(
        db_session, conversation=c1, assignee_id=owner.user.id
    )
    await update_assignee(
        db_session, conversation=c2, assignee_id=owner.user.id
    )
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/live_reports/grouped_conversation_metrics?group_by=assignee_id",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    # One bucket for the assignee (None bucket for the unassigned conv
    # is dropped by the listener).
    assert len(body) == 1
    bucket = body[0]
    assert bucket["assignee_id"] == owner.user.id
    assert bucket["open"] == 2
    assert bucket["unattended"] == 2
    assert bucket["unassigned"] == 0


async def test_grouped_by_team(client, db_session):
    owner, headers = await _seed_admin(db_session, "-gt")
    # Create a team
    team = Team(
        account_id=owner.account.id, name="Triage"
    )
    db_session.add(team)
    await db_session.flush()
    await db_session.refresh(team)

    c1 = await _seed_conversation(db_session, owner)
    c2 = await _seed_conversation(db_session, owner)
    await update_team(db_session, conversation=c1, team_id=team.id)
    await update_team(db_session, conversation=c2, team_id=team.id)
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/live_reports/grouped_conversation_metrics?group_by=team_id",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    bucket = body[0]
    assert bucket["team_id"] == team.id
    assert bucket["open"] == 2
