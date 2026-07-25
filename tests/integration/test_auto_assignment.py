"""Integration tests for the AutoAssignmentHandler hook surface.

Covers the v1 round-robin path through the three trigger points:

  * ``create_conversation`` — fresh conversation on an inbox with
    auto-assign enabled lands on a rotating member.
  * ``update_team`` — assigning a team-with-allow_auto_assign hands
    the conversation off to a team∩inbox member.
  * ``toggle_status`` re-open — when the existing assignee left the
    inbox, the re-open path picks a fresh agent.

Anchors:
  * ``AutoAssignmentHandler`` (v1 branch)
  * ``AutoAssignment::AgentAssignmentService``
  * ``InboxRoundRobinService``
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
from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_RESOLVED,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
    toggle_status,
    update_team,
)
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams.models import Team, TeamMember
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


async def _mint_headers(db_session, user) -> dict[str, str]:
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture(autouse=True)
async def _reset_round_robin_queues() -> AsyncIterator[None]:
    """Drop ROUND_ROBIN_AGENTS:* between tests.

    The Redis broadcaster is reset by ``_reset_broadcaster_per_test``
    (queue keys live on the same instance though, so we still need to
    flush the lists). We don't have a per-test Redis namespace; the
    integration suite shares db=15 with every other test.
    """
    yield
    from app.core.realtime import get_broadcaster

    try:
        broadcaster = await get_broadcaster()
        keys = await broadcaster.redis.keys("ROUND_ROBIN_AGENTS:*")
        if keys:
            await broadcaster.redis.delete(*keys)
    except Exception:  # noqa: BLE001
        # Best-effort cleanup — don't let a Redis flake fail teardown.
        pass


@pytest.fixture
async def seeded(db_session):
    """Account + 3 agents + auto-assign API inbox + contact_inbox.

    Each agent is a member of the inbox, so the round-robin queue has
    three candidates for create-conversation tests.
    """
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@auto.example.com",
            account_name="Auto Inc",
            user_full_name="Admin Auto",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    agents: list = []
    for n in (1, 2, 3):
        side = await AccountBuilder(
            db_session,
            AccountBuilderParams(
                email=f"agent{n}@auto.example.com",
                account_name=f"Side {n}",
                user_full_name=f"Agent {n}",
                user_password="Password123!",
                confirmed=True,
            ),
        ).perform()
        db_session.add(
            AccountUser(
                account_id=owner.account.id,
                user_id=side.user.id,
                role=ACCOUNT_USER_ROLE_AGENT,
            )
        )
        agents.append(side)

    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Auto Inbox",
                channel_type="api",
                channel_params={"webhook_url": "https://example.com/h"},
            ),
        ).perform()
    ).inbox

    # InboxBuilder seeds the creator (owner) as a member by default; add
    # the three agents.
    for ag in agents:
        db_session.add(InboxMember(inbox_id=inbox.id, user_id=ag.user.id))
    await db_session.flush()

    contact = Contact(
        account_id=owner.account.id,
        email="c@auto.example.com",
        name="Auto Contact",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox
    ).perform()
    headers = await _mint_headers(db_session, owner.user)
    return owner, agents, inbox, contact, ci, headers


# ---------------------------------------------------------------------------
# create_conversation
# ---------------------------------------------------------------------------
async def test_create_conversation_assigns_round_robin(
    seeded, db_session
):
    """Mirror ``run_auto_assignment`` after_save — every fresh
    conversation on an auto-assign-enabled inbox lands on a rotating
    member from the inbox pool."""
    _, _agents, _, _, ci, _ = seeded

    conv1 = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    assert conv1.assignee_id is not None
    # The owner is also an inbox member (auto-seeded by InboxBuilder),
    # so the assignee may be the owner OR any of the three agents.
    # We only assert "someone in the inbox got picked".
    member_user_ids = (
        await db_session.exec(
            __import__(
                "sqlmodel", fromlist=["select"]
            ).select(InboxMember.user_id).where(InboxMember.inbox_id == conv1.inbox_id)
        )
    ).all()
    assert conv1.assignee_id in {int(uid) for uid in member_user_ids}


async def test_create_conversation_with_explicit_assignee_skips_round_robin(
    seeded, db_session
):
    """When the builder receives an ``assignee_id`` the handler's
    ``should_run_auto_assignment?`` returns false (assignee present
    + member of inbox)."""
    _owner, agents, _inbox, _, ci, _ = seeded
    assignee = agents[0].user

    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(assignee_id=assignee.id),
    )
    # Builder honored the explicit value; auto-assign no-op'd.
    assert conv.assignee_id == assignee.id


async def test_create_conversation_skips_when_inbox_disables_auto_assign(
    seeded, db_session
):
    _owner, _, inbox, _, ci, _ = seeded
    inbox.enable_auto_assignment = False
    db_session.add(inbox)
    await db_session.flush()

    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    assert conv.assignee_id is None


async def test_full_rotation_visits_each_member(seeded, db_session):
    """Three back-to-back conversations on a 4-member inbox (3 agents +
    seeded owner) get distinct assignees on the first pass — pinning
    the round-robin's no-double-pick guarantee."""
    _, _agents, inbox, contact, _, _ = seeded
    # Build fresh contact_inboxes per conversation so we don't trip
    # ``lock_to_single_conversation`` (default is false on API inboxes
    # but be defensive anyway).
    chosen_ids: list[int] = []
    for _ in range(3):
        ci_n = await ContactInboxBuilder(
            session=db_session, contact=contact, inbox=inbox
        ).perform()
        conv = await create_conversation(
            db_session,
            contact_inbox=ci_n,
            params=ConversationBuilderParams(),
        )
        assert conv.assignee_id is not None
        chosen_ids.append(conv.assignee_id)

    # Three picks → three distinct user_ids.
    assert len(set(chosen_ids)) == 3


# ---------------------------------------------------------------------------
# update_team
# ---------------------------------------------------------------------------
async def test_update_team_picks_team_member(seeded, db_session):
    """When the new team allows auto-assign, the round-robin pool
    narrows to ``team.members ∩ inbox.members``."""
    owner, agents, _inbox, _, ci, _ = seeded
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    # Disregard whatever the create-time round-robin picked — we want
    # to test the team branch in isolation, so clear it.
    conv.assignee_id = None
    db_session.add(conv)
    await db_session.flush()

    team = Team(
        name="Platinum", account_id=owner.account.id, allow_auto_assign=True
    )
    db_session.add(team)
    await db_session.flush()
    # Only agent[1] is a team member.
    only_member = agents[1].user
    db_session.add(TeamMember(team_id=team.id, user_id=only_member.id))
    await db_session.flush()

    await update_team(db_session, conversation=conv, team_id=team.id)
    await db_session.refresh(conv)

    assert conv.team_id == team.id
    assert conv.assignee_id == only_member.id


async def test_update_team_with_disallowed_auto_assign_keeps_unassigned(
    seeded, db_session
):
    """``team.allow_auto_assign == False`` -> empty candidate list ->
    no auto-assign."""
    owner, agents, _, _, ci, _ = seeded
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    conv.assignee_id = None
    db_session.add(conv)
    await db_session.flush()

    team = Team(
        name="Gold", account_id=owner.account.id, allow_auto_assign=False
    )
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=agents[0].user.id))
    await db_session.flush()

    await update_team(db_session, conversation=conv, team_id=team.id)
    await db_session.refresh(conv)
    assert conv.team_id == team.id
    assert conv.assignee_id is None


# ---------------------------------------------------------------------------
# toggle_status (re-open)
# ---------------------------------------------------------------------------
async def test_toggle_status_reopen_reassigns_when_assignee_left_inbox(
    seeded, db_session
):
    """Mirror ``should_run_auto_assignment? -> assignee.blank? ||
    inbox.members.exclude?(assignee)``. We resolve, then drop the
    assignee from the inbox, then re-open. The handler picks a fresh
    agent from the remaining members."""
    _owner, agents, inbox, _, ci, _ = seeded
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(
            assignee_id=agents[0].user.id,
        ),
    )

    # Resolve.
    conv = await toggle_status(
        db_session, conversation=conv, status="resolved"
    )
    assert conv.status == CONVERSATION_STATUS_RESOLVED

    # Remove the assignee from the inbox.
    member_row = (
        await db_session.exec(
            __import__(
                "sqlmodel", fromlist=["select"]
            ).select(InboxMember).where(
                InboxMember.inbox_id == inbox.id,
                InboxMember.user_id == agents[0].user.id,
            )
        )
    ).first()
    if member_row is not None:
        await db_session.delete(member_row)
        await db_session.flush()

    # Re-open — the auto-assignment hook should swap to a still-member.
    conv = await toggle_status(
        db_session, conversation=conv, status="open"
    )
    assert conv.status == CONVERSATION_STATUS_OPEN
    assert conv.assignee_id != agents[0].user.id
    # Picked must be a current member.
    member_user_ids = (
        await db_session.exec(
            __import__(
                "sqlmodel", fromlist=["select"]
            ).select(InboxMember.user_id).where(InboxMember.inbox_id == inbox.id)
        )
    ).all()
    assert conv.assignee_id in {int(uid) for uid in member_user_ids}
