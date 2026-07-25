"""Integration tests for Working Hours.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/working_hours_controller.rb
  reference/chatwoot/app/models/concerns/out_of_offisable.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
    toggle_status,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.reporting.models import ReportingEvent
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.domains.working_hours.models import WorkingHour
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
            email=f"admin{suffix}@wh.example.com",
            account_name=f"WH{suffix}",
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
            email=f"agent{suffix}@wh.example.com",
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
# Defaults seeded on inbox create
# ---------------------------------------------------------------------------
async def test_inbox_create_seeds_default_schedule(db_session):
    owner, _ = await _seed_admin(db_session, "-def")
    inbox = await _seed_inbox(db_session, owner)
    rows = list(
        (
            await db_session.exec(
                select(WorkingHour).where(WorkingHour.inbox_id == inbox.id)
            )
        ).all()
    )
    assert len(rows) == 7
    by_day = {r.day_of_week: r for r in rows}
    # Sun + Sat closed.
    assert by_day[0].closed_all_day is True
    assert by_day[6].closed_all_day is True
    # Mon-Fri 9-5.
    for d in (1, 2, 3, 4, 5):
        assert by_day[d].closed_all_day is False
        assert by_day[d].open_hour == 9
        assert by_day[d].close_hour == 17


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------
async def test_index_requires_admin(client, db_session):
    owner, _ = await _seed_admin(db_session, "-ag")
    _agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, "-ag"
    )
    inbox = await _seed_inbox(db_session, owner)
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/working_hours",
        headers=agent_headers,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Read + bulk update
# ---------------------------------------------------------------------------
async def test_index_returns_seven_rows(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ix")
    inbox = await _seed_inbox(db_session, owner)
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/working_hours",
        headers=headers,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 7
    assert {r["day_of_week"] for r in rows} == {0, 1, 2, 3, 4, 5, 6}


async def test_bulk_update_changes_schedule(client, db_session):
    owner, headers = await _seed_admin(db_session, "-bu")
    inbox = await _seed_inbox(db_session, owner)
    # Override Monday to 10:30-18:00.
    body = {
        "working_hours": [
            {
                "day_of_week": 1,
                "closed_all_day": False,
                "open_hour": 10,
                "open_minutes": 30,
                "close_hour": 18,
                "close_minutes": 0,
                "open_all_day": False,
            }
        ]
    }
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/working_hours",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    rows = {r["day_of_week"]: r for r in resp.json()}
    assert rows[1]["open_hour"] == 10
    assert rows[1]["open_minutes"] == 30
    assert rows[1]["close_hour"] == 18


async def test_bulk_update_rejects_close_before_open(client, db_session):
    owner, headers = await _seed_admin(db_session, "-bad")
    inbox = await _seed_inbox(db_session, owner)
    body = {
        "working_hours": [
            {
                "day_of_week": 2,
                "closed_all_day": False,
                "open_hour": 18,
                "open_minutes": 0,
                "close_hour": 9,
                "close_minutes": 0,
                "open_all_day": False,
            }
        ]
    }
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/working_hours",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Single-row update
# ---------------------------------------------------------------------------
async def test_single_update_changes_one_day(client, db_session):
    owner, headers = await _seed_admin(db_session, "-sr")
    inbox = await _seed_inbox(db_session, owner)
    # Locate the Sunday row (closed by default) and open it all day.
    sun = (
        await db_session.exec(
            select(WorkingHour).where(
                WorkingHour.inbox_id == inbox.id,
                WorkingHour.day_of_week == 0,
            )
        )
    ).first()
    assert sun is not None
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/working_hours/{sun.id}",
        json={
            "working_hour": {
                "closed_all_day": False,
                "open_all_day": True,
            }
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["open_all_day"] is True
    assert body["closed_all_day"] is False
    assert body["open_hour"] == 0
    assert body["close_hour"] == 23


async def test_single_update_rejects_open_and_closed_simultaneously(
    client, db_session
):
    owner, headers = await _seed_admin(db_session, "-bo")
    inbox = await _seed_inbox(db_session, owner)
    mon = (
        await db_session.exec(
            select(WorkingHour).where(
                WorkingHour.inbox_id == inbox.id,
                WorkingHour.day_of_week == 1,
            )
        )
    ).first()
    assert mon is not None
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/working_hours/{mon.id}",
        json={
            "working_hour": {
                "closed_all_day": True,
                "open_all_day": True,
            }
        },
        headers=headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Business-hours math wired into Phase 7 reporting
# ---------------------------------------------------------------------------
async def test_business_hours_falls_back_when_disabled(db_session):
    """``inbox.working_hours_enabled = False`` → bh_value equals
    raw value. The default state on a fresh inbox."""
    owner, _ = await _seed_admin(db_session, "-bf")
    inbox = await _seed_inbox(db_session, owner)
    # Disabled by default.
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    conv.created_at = datetime.now(UTC) - timedelta(seconds=120)
    db_session.add(conv)
    await db_session.flush()
    await toggle_status(db_session, conversation=conv, status="resolved")

    event = (
        await db_session.exec(
            select(ReportingEvent).where(
                ReportingEvent.conversation_id == conv.id,
                ReportingEvent.name == "conversation_resolved",
            )
        )
    ).first()
    assert event is not None
    assert event.value_in_business_hours == event.value


async def test_business_hours_truncates_when_outside_schedule(db_session):
    """An event whose start..end falls entirely OUTSIDE working hours
    yields ``value_in_business_hours == 0`` while preserving the raw
    duration in ``value``."""
    owner, _ = await _seed_admin(db_session, "-tr")
    inbox = await _seed_inbox(db_session, owner)
    # Enable working hours but mark every day as closed.
    inbox.working_hours_enabled = True
    inbox.timezone = "UTC"
    db_session.add(inbox)
    await db_session.flush()
    # Force every day closed.
    rows = list(
        (
            await db_session.exec(
                select(WorkingHour).where(WorkingHour.inbox_id == inbox.id)
            )
        ).all()
    )
    for r in rows:
        r.closed_all_day = True
        r.open_all_day = False
        db_session.add(r)
    await db_session.flush()

    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    conv.created_at = datetime.now(UTC) - timedelta(seconds=300)
    db_session.add(conv)
    await db_session.flush()
    await toggle_status(db_session, conversation=conv, status="resolved")

    event = (
        await db_session.exec(
            select(ReportingEvent).where(
                ReportingEvent.conversation_id == conv.id,
                ReportingEvent.name == "conversation_resolved",
            )
        )
    ).first()
    assert event is not None
    assert event.value >= 300
    assert event.value_in_business_hours == 0
