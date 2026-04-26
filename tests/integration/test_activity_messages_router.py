"""Integration tests for the Phase 4b.3 activity-message endpoints.

Covers:
  * ``POST /conversations/:id/assignments`` — agent + team branches.
  * ``GET  /conversations/:id/labels``      — payload list.
  * ``POST /conversations/:id/labels``      — replace label set.
  * Activity-row side-effects on toggle_status / toggle_priority /
    mute / unmute / assignee / team / labels — i.e. confirm an
    ``message_type=activity`` row landed with the expected content
    string.

Anchors:
  * ``Api::V1::Accounts::Conversations::AssignmentsController#create``
  * ``Api::V1::Accounts::Conversations::LabelsController#index/create``
  * ``ActivityMessageHandler`` + the per-event concerns.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_TYPE_ACTIVITY,
    Conversation,
    ConversationLabel,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.labels.models import Label
from app.domains.teams.models import Team, TeamMember
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_AGENT,
    AccountUser,
)
from app.main import app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures (parallel to test_conversations_router.py — kept local so the
# two suites can evolve independently)
# ---------------------------------------------------------------------------
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
            email="admin@act.example.com",
            account_name="Activity Inc",
            user_full_name="Admin Activity",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent_b = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@act.example.com",
            account_name="Side Account",
            user_full_name="Agent Beta",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=agent_b.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    inbox_result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API Inbox",
            channel_type="api",
            channel_params={"webhook_url": "https://example.com/h"},
        ),
    ).perform()
    contact = Contact(
        account_id=owner.account.id,
        email="c@act.example.com",
        name="Activity Contact",
    )
    db_session.add(contact)
    await db_session.flush()
    contact_inbox = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox_result.inbox
    ).perform()
    admin_h = await _mint_headers(db_session, owner.user)
    return owner, agent_b, inbox_result.inbox, contact, contact_inbox, admin_h


async def _make_conv(db_session, *, contact_inbox) -> Conversation:
    return await create_conversation(
        db_session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(),
    )


async def _activities_on(db_session, conv: Conversation) -> list[Message]:
    rows = (
        await db_session.exec(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .where(Message.message_type == MESSAGE_TYPE_ACTIVITY)
            .order_by(Message.id)
        )
    ).all()
    return list(rows)


# ---------------------------------------------------------------------------
# toggle_status -> activity row
# ---------------------------------------------------------------------------
async def test_toggle_status_inserts_activity_row(client, seeded, db_session):
    """Mirrors ``ActivityMessageHandler#handle_status_change`` — a status
    flip writes one ``message_type=activity`` row whose content matches
    the en.yml ``conversations.activity.status.<new>`` template."""
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/toggle_status",
        json={},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text

    rows = await _activities_on(db_session, conv)
    # Exactly one activity row for the open->resolved flip.
    assert len(rows) == 1
    assert rows[0].content == "Conversation was marked resolved by Admin Activity"


# ---------------------------------------------------------------------------
# toggle_priority -> activity row
# ---------------------------------------------------------------------------
async def test_toggle_priority_added_inserts_activity(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/toggle_priority",
        json={"priority": "urgent"},
        headers=admin_h,
    )
    assert resp.status_code == 200

    rows = await _activities_on(db_session, conv)
    assert len(rows) == 1
    assert rows[0].content == "Admin Activity set the priority to urgent"


# ---------------------------------------------------------------------------
# mute / unmute -> activity rows
# ---------------------------------------------------------------------------
async def test_mute_inserts_status_then_muted_activity(client, seeded, db_session):
    """Mute = (toggle_status -> resolved) + muted activity. Two rows total."""
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/mute",
        headers=admin_h,
    )
    assert resp.status_code == 200

    rows = await _activities_on(db_session, conv)
    contents = [r.content for r in rows]
    assert contents == [
        "Conversation was marked resolved by Admin Activity",
        "Admin Activity has muted the conversation",
    ]


async def test_unmute_inserts_unmuted_activity(client, seeded, db_session):
    owner, _, _, contact, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)
    contact.blocked = True
    db_session.add(contact)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/unmute",
        headers=admin_h,
    )
    assert resp.status_code == 200
    rows = await _activities_on(db_session, conv)
    assert [r.content for r in rows] == [
        "Admin Activity has unmuted the conversation"
    ]


# ---------------------------------------------------------------------------
# Assignments — agent
# ---------------------------------------------------------------------------
async def test_assignments_agent_renders_partial_and_writes_activity(
    client, seeded, db_session
):
    """``POST /assignments`` with ``assignee_id`` returns the agent
    partial and inserts the assigned-to activity row."""
    owner, agent, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/assignments",
        json={"assignee_id": agent.user.id},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == agent.user.id
    assert body["name"] == "Agent Beta"
    assert body["account_id"] == owner.account.id

    rows = await _activities_on(db_session, conv)
    assert len(rows) == 1
    assert rows[0].content == "Assigned to Agent Beta by Admin Activity"


async def test_assignments_self_assigned_template(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/assignments",
        json={"assignee_id": owner.user.id},
        headers=admin_h,
    )
    assert resp.status_code == 200
    rows = await _activities_on(db_session, conv)
    assert rows[0].content == "Admin Activity self-assigned this conversation"


async def test_assignments_unassign(client, seeded, db_session):
    owner, agent, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)
    conv.assignee_id = agent.user.id
    db_session.add(conv)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/assignments",
        json={"assignee_id": None},
        headers=admin_h,
    )
    assert resp.status_code == 200
    rows = await _activities_on(db_session, conv)
    assert rows[0].content == "Conversation unassigned by Admin Activity"


async def test_assignments_unknown_user_returns_null(client, seeded, db_session):
    """Mirrors Rails: ``conversation.account.users.find_by(id:)`` returns
    nil for users outside the account, the controller renders ``json: nil``."""
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/assignments",
        json={"assignee_id": 999999},
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json() is None


# ---------------------------------------------------------------------------
# Assignments — team
# ---------------------------------------------------------------------------
async def test_assignments_team_writes_activity(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)

    team = Team(name="Support", account_id=owner.account.id)
    db_session.add(team)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/assignments",
        json={"team_id": team.id},
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == team.id
    assert body["name"] == "Support"

    rows = await _activities_on(db_session, conv)
    assert rows[0].content == "Assigned to Support by Admin Activity"


async def test_assignments_team_clears_non_member_assignee(
    client, seeded, db_session
):
    """``ensure_assignee_is_from_team``: if the new team's members don't
    include the current assignee, drop the assignee."""
    owner, agent, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)
    conv.assignee_id = agent.user.id
    db_session.add(conv)

    team = Team(name="Sales", account_id=owner.account.id)
    db_session.add(team)
    await db_session.flush()
    # NOTE: agent is NOT a TeamMember.

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/assignments",
        json={"team_id": team.id},
        headers=admin_h,
    )
    assert resp.status_code == 200

    await db_session.refresh(conv)
    assert conv.team_id == team.id
    assert conv.assignee_id is None  # cleared by team-membership guard


async def test_assignments_team_keeps_member_assignee_with_assignee_template(
    client, seeded, db_session
):
    """When the new team has the assignee as a member, the
    ``assigned_with_assignee`` template wins (assignee_id stays put)."""
    owner, agent, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)
    conv.assignee_id = agent.user.id
    db_session.add(conv)

    team = Team(name="Support", account_id=owner.account.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=agent.user.id))
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/assignments",
        json={"team_id": team.id},
        headers=admin_h,
    )
    assert resp.status_code == 200

    await db_session.refresh(conv)
    assert conv.team_id == team.id
    assert conv.assignee_id == agent.user.id

    rows = await _activities_on(db_session, conv)
    # Just the team change activity — the assignee didn't actually change
    # so we use the simple "Assigned to {team_name} by ..." template.
    assert rows[-1].content == "Assigned to Support by Admin Activity"


async def test_assignments_no_keys_returns_null(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/assignments",
        json={},
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json() is None


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
async def test_labels_index_empty(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/labels",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json() == {"payload": []}


async def test_labels_create_replaces_set_and_writes_activity(
    client, seeded, db_session
):
    """A label write auto-creates the Label rows, replaces the join set,
    and inserts an ``added`` activity row with the diff list."""
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/labels",
        json={"labels": ["urgent", "billing"]},
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json() == {"payload": ["urgent", "billing"]}

    # Label rows auto-created on this account
    label_titles = sorted(
        r.title
        for r in (
            await db_session.exec(
                select(Label).where(Label.account_id == owner.account.id)
            )
        ).all()
    )
    assert label_titles == ["billing", "urgent"]

    # Join rows
    joins = list(
        (
            await db_session.exec(
                select(ConversationLabel).where(
                    ConversationLabel.conversation_id == conv.id
                )
            )
        ).all()
    )
    assert len(joins) == 2

    # Cached CSV updated
    await db_session.refresh(conv)
    assert conv.cached_label_list == "urgent,billing"

    # Activity row
    rows = await _activities_on(db_session, conv)
    assert len(rows) == 1
    assert rows[0].content == "Admin Activity added urgent, billing"


async def test_labels_diff_emits_added_and_removed_separately(
    client, seeded, db_session
):
    """Replacing {a,b} with {b,c} fires one ``added`` row for [c] and
    one ``removed`` row for [a] — mirrors the two
    ``create_label_change_activity`` calls in Rails."""
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)

    # First write: a, b
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/labels",
        json={"labels": ["a", "b"]},
        headers=admin_h,
    )
    # Second write: b, c
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/labels",
        json={"labels": ["b", "c"]},
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json() == {"payload": ["b", "c"]}

    contents = [r.content for r in await _activities_on(db_session, conv)]
    # Initial add row, then add[c] + remove[a].
    assert contents == [
        "Admin Activity added a, b",
        "Admin Activity added c",
        "Admin Activity removed a",
    ]


async def test_labels_idempotent_no_diff_no_activity(
    client, seeded, db_session
):
    owner, _, _, _, contact_inbox, admin_h = seeded
    conv = await _make_conv(db_session, contact_inbox=contact_inbox)

    await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/labels",
        json={"labels": ["a", "b"]},
        headers=admin_h,
    )
    rows_before = await _activities_on(db_session, conv)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/labels",
        json={"labels": ["a", "b"]},  # identical set
        headers=admin_h,
    )
    assert resp.status_code == 200
    rows_after = await _activities_on(db_session, conv)
    assert rows_after == rows_before  # no new activity rows
