"""Integration tests for the per-entity summary reports.

Anchors:
  reference/chatwoot/app/controllers/api/v2/accounts/summary_reports_controller.rb
  reference/chatwoot/app/builders/v2/reports/agent_summary_builder.rb
  reference/chatwoot/app/builders/v2/reports/team_summary_builder.rb
  reference/chatwoot/app/builders/v2/reports/inbox_summary_builder.rb
  reference/chatwoot/app/builders/v2/reports/label_summary_builder.rb
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
    update_labels,
    update_team,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.labels.models import Label
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
            email=f"admin{suffix}@es.example.com",
            account_name=f"ES{suffix}",
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
# Auth
# ---------------------------------------------------------------------------
async def test_agent_summary_requires_auth(client):
    resp = await client.get(
        "/api/v2/accounts/1/summary_reports/agent"
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Agent summary
# ---------------------------------------------------------------------------
async def test_agent_summary_lists_account_members_with_zeros(
    client, db_session
):
    owner, headers = await _seed_admin(db_session, "-ag")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/summary_reports/agent",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    row = body[0]
    assert row["id"] == owner.user.id
    assert row["conversations_count"] == 0
    assert row["resolved_conversations_count"] == 0
    assert row["avg_resolution_time"] == 0
    assert row["avg_first_response_time"] == 0
    assert row["avg_reply_time"] == 0


async def test_agent_summary_counts_assigned_resolutions(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ar")
    conv = await _seed_conversation(db_session, owner)
    await update_assignee(
        db_session, conversation=conv, assignee_id=owner.user.id
    )
    await toggle_status(db_session, conversation=conv, status="resolved")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/summary_reports/agent",
        headers=headers,
    )
    body = resp.json()
    row = next(r for r in body if r["id"] == owner.user.id)
    assert row["conversations_count"] == 1
    assert row["resolved_conversations_count"] == 1


# ---------------------------------------------------------------------------
# Team summary
# ---------------------------------------------------------------------------
async def test_team_summary_empty_account(client, db_session):
    owner, headers = await _seed_admin(db_session, "-tx")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/summary_reports/team",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_team_summary_counts_conversations(client, db_session):
    owner, headers = await _seed_admin(db_session, "-tc")
    team = Team(account_id=owner.account.id, name="Triage")
    db_session.add(team)
    await db_session.flush()
    await db_session.refresh(team)
    conv = await _seed_conversation(db_session, owner)
    await update_team(db_session, conversation=conv, team_id=team.id)
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/summary_reports/team",
        headers=headers,
    )
    body = resp.json()
    assert len(body) == 1
    row = body[0]
    assert row["id"] == team.id
    assert row["name"] == "Triage"
    assert row["conversations_count"] == 1


# ---------------------------------------------------------------------------
# Inbox summary
# ---------------------------------------------------------------------------
async def test_inbox_summary_returns_rows_per_inbox(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ib")
    a = await _seed_conversation(db_session, owner)
    b = await _seed_conversation(db_session, owner)  # different inbox
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/summary_reports/inbox",
        headers=headers,
    )
    body = resp.json()
    # Two inboxes, each with one conversation.
    by_id = {row["id"]: row for row in body}
    assert by_id[a.inbox_id]["conversations_count"] == 1
    assert by_id[b.inbox_id]["conversations_count"] == 1


# ---------------------------------------------------------------------------
# Label summary
# ---------------------------------------------------------------------------
async def test_label_summary_empty_when_no_labels(client, db_session):
    owner, headers = await _seed_admin(db_session, "-lex")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/summary_reports/label",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_label_summary_counts_tagged_conversations(client, db_session):
    owner, headers = await _seed_admin(db_session, "-lc")
    # Two conversations, both tagged ``vip``; one resolved.
    c1 = await _seed_conversation(db_session, owner)
    c2 = await _seed_conversation(db_session, owner)
    await update_labels(db_session, conversation=c1, titles=["vip"])
    await update_labels(db_session, conversation=c2, titles=["vip"])
    await toggle_status(db_session, conversation=c2, status="resolved")

    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/summary_reports/label",
        headers=headers,
    )
    body = resp.json()
    assert len(body) == 1
    row = body[0]
    assert row["name"] == "vip"
    assert row["conversations_count"] == 2
    assert row["resolved_conversations_count"] == 1
