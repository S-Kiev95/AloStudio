"""Integration tests for the Instagram publishing REST endpoints (I.2).

Covers auth gates + scheduling validation + the scheduled (non-fired)
path. The full immediate-publish orchestration is tested separately in
``test_instagram_publisher.py`` at the service level (where respx +
the test session compose cleanly without the worker's separate
engine).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
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
            email=f"admin{suffix}@igr.example.com",
            account_name=f"IGR{suffix}",
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


async def _seed_ig_inbox(db_session, owner, suffix: str):
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": f"ig-{suffix}",
                "access_token": "PAGE-TOKEN",
                "expires_at": (
                    datetime.now(UTC) + timedelta(days=60)
                ).isoformat(),
            },
        ),
    ).perform()
    return result.inbox


async def _seed_api_inbox(db_session, owner, suffix: str):
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"API{suffix}",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    return result.inbox


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def test_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/instagram_posts")
    assert resp.status_code == 401


async def test_create_blocked_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, "-ag")
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent-ag@igr.example.com",
            account_name="Other",
            user_full_name="Agent",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
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
    inbox = await _seed_ig_inbox(db_session, owner, "-ag")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": inbox.id,
            "media_type": "IMAGE",
            "source": {"image_url": "https://x.example.com/p.jpg"},
        },
        headers=headers.as_response_headers(),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Scheduling validation
# ---------------------------------------------------------------------------
async def test_scheduled_in_past_rejected(client, db_session):
    owner, headers = await _seed_admin(db_session, "-past")
    inbox = await _seed_ig_inbox(db_session, owner, "-past")
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": inbox.id,
            "media_type": "IMAGE",
            "source": {"image_url": "https://x.example.com/p.jpg"},
            "scheduled_for": past,
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert "future" in resp.json()["message"]


async def test_scheduled_in_future_creates_pending_not_fired(
    client, db_session
):
    """A future-scheduled post stays ``pending`` and is NOT enqueued —
    the scheduler picks it up at fire time. No Meta call happens."""
    owner, headers = await _seed_admin(db_session, "-fut")
    inbox = await _seed_ig_inbox(db_session, owner, "-fut")
    future = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": inbox.id,
            "media_type": "IMAGE",
            "source": {"image_url": "https://x.example.com/p.jpg"},
            "caption": "scheduled",
            "scheduled_for": future,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == "pending"
    assert body["scheduled_for"] is not None
    assert body["ig_media_id"] is None


async def test_create_far_future_no_cap(client, db_session):
    """No upper-bound cap — scheduling 2 years out is accepted."""
    owner, headers = await _seed_admin(db_session, "-far")
    inbox = await _seed_ig_inbox(db_session, owner, "-far")
    far = (datetime.now(UTC) + timedelta(days=730)).isoformat()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": inbox.id,
            "media_type": "IMAGE",
            "source": {"image_url": "https://x.example.com/p.jpg"},
            "scheduled_for": far,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "pending"


# ---------------------------------------------------------------------------
# Inbox validation
# ---------------------------------------------------------------------------
async def test_non_instagram_inbox_rejected(client, db_session):
    owner, headers = await _seed_admin(db_session, "-noig")
    api_inbox = await _seed_api_inbox(db_session, owner, "-noig")
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": api_inbox.id,
            "media_type": "IMAGE",
            "source": {"image_url": "https://x.example.com/p.jpg"},
            "scheduled_for": future,
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert "not an Instagram inbox" in resp.json()["message"]


async def test_unknown_inbox_404(client, db_session):
    owner, headers = await _seed_admin(db_session, "-unk")
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": 999999,
            "media_type": "IMAGE",
            "source": {"image_url": "https://x.example.com/p.jpg"},
            "scheduled_for": future,
        },
        headers=headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Source validation (delegated to service)
# ---------------------------------------------------------------------------
async def test_image_without_url_rejected(client, db_session):
    owner, headers = await _seed_admin(db_session, "-noimg")
    inbox = await _seed_ig_inbox(db_session, owner, "-noimg")
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": inbox.id,
            "media_type": "IMAGE",
            "source": {"caption_only": "no url"},
            "scheduled_for": future,
        },
        headers=headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# index + show
# ---------------------------------------------------------------------------
async def test_index_and_show(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ix")
    inbox = await _seed_ig_inbox(db_session, owner, "-ix")
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": inbox.id,
            "media_type": "IMAGE",
            "source": {"image_url": "https://x.example.com/p.jpg"},
            "scheduled_for": future,
        },
        headers=headers,
    )
    post_id = create.json()["id"]

    index = await client.get(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        headers=headers,
    )
    assert index.status_code == 200
    assert any(p["id"] == post_id for p in index.json())

    show = await client.get(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts/{post_id}",
        headers=headers,
    )
    assert show.status_code == 200
    assert show.json()["id"] == post_id
    assert "containers" in show.json()
