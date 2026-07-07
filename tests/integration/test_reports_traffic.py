"""Integration tests for the conversation-traffic heatmap.

``GET /api/v2/accounts/{id}/reports/conversation_traffic`` buckets
conversations by (local date, hour-of-day) at the caller's UTC offset.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

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


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@tr.example.com",
            account_name=f"TR{suffix}",
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

    inbox = (
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
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{suffix}",
    ).perform()
    return owner, headers.as_response_headers(), ci


async def _conv_at(db_session, ci, when: datetime):
    # create_conversation reads contact_inbox.inbox — load the relationship
    # in async context first (see reference_live_verify_recipe / memory).
    await db_session.refresh(ci, ["inbox"])
    conv = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )
    conv.created_at = when
    db_session.add(conv)
    await db_session.flush()
    return conv


def _unix(dt: datetime) -> str:
    return str(int(dt.timestamp()))


async def test_traffic_buckets_by_local_hour(client, db_session):
    owner, headers, ci = await _seed(db_session, "-h")
    # Two conversations in hour 10 (UTC), one in hour 14, on 2026-07-01.
    await _conv_at(db_session, ci, datetime(2026, 7, 1, 10, 15, tzinfo=UTC))
    await _conv_at(db_session, ci, datetime(2026, 7, 1, 10, 45, tzinfo=UTC))
    await _conv_at(db_session, ci, datetime(2026, 7, 1, 14, 0, tzinfo=UTC))

    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/conversation_traffic"
        f"?since={_unix(datetime(2026, 7, 1, tzinfo=UTC))}"
        f"&until={_unix(datetime(2026, 7, 2, tzinfo=UTC))}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["data"]) == 1
    row = body["data"][0]
    assert row["date"] == "2026-07-01"
    assert len(row["hours"]) == 24
    assert row["hours"][10] == 2
    assert row["hours"][14] == 1
    assert sum(row["hours"]) == 3


async def test_traffic_respects_timezone_offset(client, db_session):
    owner, headers, ci = await _seed(db_session, "-tz")
    # 01:00 UTC on 2026-07-02 → at UTC-3 that's 22:00 on 2026-07-01.
    await _conv_at(db_session, ci, datetime(2026, 7, 2, 1, 0, tzinfo=UTC))

    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/conversation_traffic"
        f"?since={_unix(datetime(2026, 7, 1, tzinfo=UTC))}"
        f"&until={_unix(datetime(2026, 7, 3, tzinfo=UTC))}"
        "&timezone_offset=-3",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["timezone_offset"] == -3
    by_date = {r["date"]: r["hours"] for r in body["data"]}
    assert by_date["2026-07-01"][22] == 1
