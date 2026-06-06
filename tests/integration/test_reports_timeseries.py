"""Integration tests for the timeseries report endpoint.

Anchors:
  reference/chatwoot/app/builders/v2/reports/timeseries/count_report_builder.rb
  reference/chatwoot/app/builders/v2/reports/timeseries/average_report_builder.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
    toggle_status,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
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
            email=f"admin{suffix}@ts.example.com",
            account_name=f"TS{suffix}",
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
# Validation / dispatch
# ---------------------------------------------------------------------------
async def test_requires_auth(client):
    resp = await client.get(
        "/api/v2/accounts/1/reports?metric=conversations_count"
    )
    assert resp.status_code == 401


async def test_unknown_metric_returns_empty(client, db_session):
    owner, headers = await _seed_admin(db_session, "-bm")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports?metric=frobnicate",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_missing_metric_returns_empty(client, db_session):
    owner, headers = await _seed_admin(db_session, "-nm")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Count metrics
# ---------------------------------------------------------------------------
async def test_conversations_count_buckets_by_day(client, db_session):
    owner, headers = await _seed_admin(db_session, "-cc")
    await _seed_conversation(db_session, owner)
    await _seed_conversation(db_session, owner)
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports"
        "?metric=conversations_count",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    # Both conversations land in today's bucket.
    assert len(body) == 1
    assert body[0]["value"] == 2
    assert "timestamp" in body[0]
    # Count metric has no ``count`` key.
    assert "count" not in body[0]


# ---------------------------------------------------------------------------
# Timezone bucketing (regression: R1 half-hour zones + R2 label off-by-one)
# ---------------------------------------------------------------------------
async def test_bucket_timestamp_is_true_local_midnight_negative_offset(
    client, db_session
):
    """R2 regression. An event at 02:00 UTC is the previous day in UTC-3
    (the Americas). The bucket must be that local day, and the emitted
    timestamp must be the day's TRUE local midnight (03:00Z for UTC-3) —
    not the naive midnight labelled UTC, which rendered one day early on
    a UTC-3 client. The pre-fix code only used tz=UTC in tests, so this
    boundary was never exercised."""
    owner, headers = await _seed_admin(db_session, "-tzneg")
    conv = await _seed_conversation(db_session, owner)
    conv.created_at = datetime(2026, 5, 15, 2, 0, tzinfo=UTC)
    db_session.add(conv)
    await db_session.flush()

    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports"
        "?metric=conversations_count&timezone_offset=-3",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    # 2026-05-14 23:00 in UTC-3 → local day 14-may → true midnight
    # 2026-05-14 00:00 −03:00 = 2026-05-14 03:00 UTC.
    expected = int(datetime(2026, 5, 14, 3, 0, tzinfo=UTC).timestamp())
    assert body[0]["timestamp"] == expected


async def test_bucket_handles_half_hour_offset(client, db_session):
    """R1 regression. A +5:30 (IST) offset must bucket at the half-hour,
    not rounded to +6. Event 2026-05-14 18:15 UTC is 23:45 IST (14-may);
    rounding to +6 would push it to 00:15 (15-may) — the wrong day. The
    fix carries the offset in minutes so the local day is 14-may."""
    owner, headers = await _seed_admin(db_session, "-tzhalf")
    conv = await _seed_conversation(db_session, owner)
    conv.created_at = datetime(2026, 5, 14, 18, 15, tzinfo=UTC)
    db_session.add(conv)
    await db_session.flush()

    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports"
        "?metric=conversations_count&timezone_offset=5.5",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    # IST local day 14-may → true midnight 2026-05-14 00:00 +05:30 =
    # 2026-05-13 18:30 UTC.
    expected = int(datetime(2026, 5, 13, 18, 30, tzinfo=UTC).timestamp())
    assert body[0]["timestamp"] == expected


async def test_incoming_outgoing_messages_count(client, db_session):
    owner, headers = await _seed_admin(db_session, "-im")
    conv = await _seed_conversation(db_session, owner)
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="a", message_type="incoming"),
        user_id=None,
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="b", message_type="incoming"),
        user_id=None,
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="c", message_type="outgoing"),
        user_id=owner.user.id,
    )
    inc = (
        await client.get(
            f"/api/v2/accounts/{owner.account.id}/reports"
            "?metric=incoming_messages_count",
            headers=headers,
        )
    ).json()
    out = (
        await client.get(
            f"/api/v2/accounts/{owner.account.id}/reports"
            "?metric=outgoing_messages_count",
            headers=headers,
        )
    ).json()
    assert inc[0]["value"] == 2
    assert out[0]["value"] == 1


async def test_resolutions_count(client, db_session):
    owner, headers = await _seed_admin(db_session, "-rc")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports"
        "?metric=resolutions_count",
        headers=headers,
    )
    body = resp.json()
    assert len(body) == 1
    assert body[0]["value"] == 1


async def test_bot_metrics_empty_in_phase_7(client, db_session):
    """``bot_resolutions_count`` / ``bot_handoffs_count`` return zero in
    7.x — Phase 8 emits the underlying events."""
    owner, headers = await _seed_admin(db_session, "-bz")
    await _seed_conversation(db_session, owner)
    br = (
        await client.get(
            f"/api/v2/accounts/{owner.account.id}/reports"
            "?metric=bot_resolutions_count",
            headers=headers,
        )
    ).json()
    bh = (
        await client.get(
            f"/api/v2/accounts/{owner.account.id}/reports"
            "?metric=bot_handoffs_count",
            headers=headers,
        )
    ).json()
    assert br == []
    assert bh == []


# ---------------------------------------------------------------------------
# Avg metrics — include ``count`` per bucket
# ---------------------------------------------------------------------------
async def test_avg_resolution_time_buckets_include_count(client, db_session):
    owner, headers = await _seed_admin(db_session, "-art")
    conv = await _seed_conversation(db_session, owner)
    conv.created_at = datetime.now(UTC) - timedelta(seconds=300)
    db_session.add(conv)
    await db_session.flush()
    await toggle_status(db_session, conversation=conv, status="resolved")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports"
        "?metric=avg_resolution_time",
        headers=headers,
    )
    body = resp.json()
    assert len(body) == 1
    bucket = body[0]
    assert bucket["value"] >= 300
    assert bucket["count"] == 1
    assert "timestamp" in bucket


async def test_reply_time_metric(client, db_session):
    owner, headers = await _seed_admin(db_session, "-rt")
    conv = await _seed_conversation(db_session, owner)
    conv.created_at = datetime.now(UTC) - timedelta(seconds=10)
    conv.waiting_since = conv.created_at
    db_session.add(conv)
    await db_session.flush()
    # First agent reply consumes the first_response event.
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="hi", message_type="outgoing"),
        user_id=owner.user.id,
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="follow up", message_type="incoming"),
        user_id=None,
    )
    await db_session.refresh(conv)
    conv.waiting_since = datetime.now(UTC) - timedelta(seconds=45)
    db_session.add(conv)
    await db_session.flush()
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="resp", message_type="outgoing"),
        user_id=owner.user.id,
    )
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports"
        "?metric=reply_time",
        headers=headers,
    )
    body = resp.json()
    assert len(body) == 1
    assert body[0]["value"] >= 45
    assert body[0]["count"] == 1


# ---------------------------------------------------------------------------
# Scope filter
# ---------------------------------------------------------------------------
async def test_timeseries_scopes_to_inbox(client, db_session):
    owner, headers = await _seed_admin(db_session, "-sc")
    a = await _seed_conversation(db_session, owner)
    await _seed_conversation(db_session, owner)
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports"
        f"?metric=conversations_count&type=inbox&id={a.inbox_id}",
        headers=headers,
    )
    body = resp.json()
    assert len(body) == 1
    assert body[0]["value"] == 1
