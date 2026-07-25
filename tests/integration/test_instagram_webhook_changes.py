"""Integration tests for the Instagram webhook ``changes`` path (I.8).

Covers the comments / mentions / story_insights routing in
``webhook_changes.process_instagram_changes`` plus the HMAC
``X-Hub-Signature-256`` gate on the shared ``POST /webhooks/instagram``
endpoint.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import publishing_service as svc
from app.domains.instagram.models import InstagramComment
from app.domains.instagram.webhook_changes import process_instagram_changes
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


@pytest.fixture
def meta_secret():
    """Turn on HMAC verification + stamp the signing secret, restoring
    both afterwards so the Phase 5e mirror tests stay unaffected."""
    settings = get_settings()
    orig_secret = settings.meta_app_secret
    orig_flag = settings.meta_verify_webhook_signature
    settings.meta_app_secret = "test-app-secret"
    settings.meta_verify_webhook_signature = True
    try:
        yield "test-app-secret"
    finally:
        settings.meta_app_secret = orig_secret
        settings.meta_verify_webhook_signature = orig_flag


async def _seed(db_session, suffix: str, *, ig_id: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igw.example.com",
            account_name=f"IGW{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": ig_id,
                "access_token": "PAGE-TOKEN",
            },
        ),
    ).perform()
    return owner, result.inbox, result.channel


# ---------------------------------------------------------------------------
# Service — comments / mentions / story_insights
# ---------------------------------------------------------------------------
async def test_comment_change_creates_row(db_session):
    _owner, _inbox, _channel = await _seed(db_session, "-cmt", ig_id="IGW1")
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IGW1",
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "CMT1",
                            "text": "love it",
                            "from": {"id": "u1", "username": "fan"},
                            "media": {"id": "MED1"},
                        },
                    }
                ],
            }
        ],
    }
    counts = await process_instagram_changes(db_session, payload=payload)
    assert counts["comments"] == 1
    row = (
        await db_session.exec(
            select(InstagramComment).where(
                InstagramComment.ig_comment_id == "CMT1"
            )
        )
    ).first()
    assert row is not None
    assert row.ig_media_id == "MED1"
    assert row.from_username == "fan"
    assert row.text == "love it"
    assert row.parent_comment_id is None


async def test_comment_reply_change_sets_parent(db_session):
    _owner, _inbox, _channel = await _seed(db_session, "-rep", ig_id="IGW2")
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IGW2",
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "RPLY1",
                            "text": "thanks",
                            "media": {"id": "MED2"},
                            "parent_id": "PARENT1",
                        },
                    }
                ],
            }
        ],
    }
    await process_instagram_changes(db_session, payload=payload)
    row = (
        await db_session.exec(
            select(InstagramComment).where(
                InstagramComment.ig_comment_id == "RPLY1"
            )
        )
    ).first()
    assert row is not None
    assert row.parent_comment_id == "PARENT1"


async def test_mention_change_creates_row(db_session):
    _owner, _inbox, _channel = await _seed(db_session, "-men", ig_id="IGW3")
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IGW3",
                "changes": [
                    {
                        "field": "mentions",
                        "value": {"media_id": "MED3", "comment_id": "MEN1"},
                    }
                ],
            }
        ],
    }
    counts = await process_instagram_changes(db_session, payload=payload)
    assert counts["mentions"] == 1
    row = (
        await db_session.exec(
            select(InstagramComment).where(
                InstagramComment.ig_comment_id == "MEN1"
            )
        )
    ).first()
    assert row is not None
    assert row.ig_media_id == "MED3"


async def test_caption_only_mention_skipped(db_session):
    _owner, _inbox, _channel = await _seed(db_session, "-capm", ig_id="IGW3b")
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IGW3b",
                "changes": [
                    {"field": "mentions", "value": {"media_id": "MEDX"}}
                ],
            }
        ],
    }
    counts = await process_instagram_changes(db_session, payload=payload)
    assert counts["mentions"] == 0


async def test_story_insights_stamps_post(db_session):
    owner, inbox, channel = await _seed(db_session, "-si", ig_id="IGW4")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="STORIES",
        source={"image_url": "https://cdn.example.com/s.jpg"},
    )
    post.state = "published"
    post.ig_media_id = "STORYMED"
    db_session.add(post)
    await db_session.flush()

    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IGW4",
                "changes": [
                    {
                        "field": "story_insights",
                        "value": {
                            "media_id": "STORYMED",
                            "impressions": 120,
                            "reach": 100,
                            "exits": 5,
                            "replies": 3,
                        },
                    }
                ],
            }
        ],
    }
    counts = await process_instagram_changes(db_session, payload=payload)
    assert counts["story_insights"] == 1
    await db_session.refresh(post)
    assert post.insights is not None
    assert post.insights["impressions"] == 120
    assert post.insights["reach"] == 100
    assert "media_id" not in post.insights


async def test_story_insights_no_post_skips(db_session):
    _owner, _inbox, _channel = await _seed(db_session, "-sino", ig_id="IGW5")
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IGW5",
                "changes": [
                    {
                        "field": "story_insights",
                        "value": {"media_id": "NOPE", "impressions": 1},
                    }
                ],
            }
        ],
    }
    counts = await process_instagram_changes(db_session, payload=payload)
    assert counts["story_insights"] == 0


async def test_unknown_account_skipped(db_session):
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "DOES-NOT-EXIST",
                "changes": [
                    {
                        "field": "comments",
                        "value": {"id": "X", "media": {"id": "Y"}},
                    }
                ],
            }
        ],
    }
    counts = await process_instagram_changes(db_session, payload=payload)
    assert counts == {"comments": 0, "mentions": 0, "story_insights": 0}


# ---------------------------------------------------------------------------
# Endpoint — HMAC gate + end-to-end routing
# ---------------------------------------------------------------------------
def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()


@pytest.mark.usefixtures("meta_secret")
async def test_webhook_rejects_bad_signature(client, meta_secret):
    body = json.dumps({"object": "instagram", "entry": []}).encode()
    resp = await client.post(
        "/webhooks/instagram",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Invalid signature"}


async def test_webhook_rejects_missing_signature_when_secret_set(
    client, meta_secret
):
    body = json.dumps({"object": "instagram", "entry": []}).encode()
    resp = await client.post(
        "/webhooks/instagram",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401


async def test_webhook_accepts_valid_signature_and_routes_comment(
    client, db_session, meta_secret
):
    await _seed(db_session, "-ep", ig_id="IGWEP")
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IGWEP",
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "EPCMT1",
                            "text": "hi",
                            "media": {"id": "EPMED"},
                        },
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload).encode()
    resp = await client.post(
        "/webhooks/instagram",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body, meta_secret),
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    row = (
        await db_session.exec(
            select(InstagramComment).where(
                InstagramComment.ig_comment_id == "EPCMT1"
            )
        )
    ).first()
    assert row is not None


async def test_webhook_no_secret_skips_hmac_and_routes(client, db_session):
    """With the default empty secret, no signature is required and the
    changes path still runs (parity-preserving)."""
    settings = get_settings()
    original = settings.meta_verify_webhook_signature
    settings.meta_verify_webhook_signature = False
    try:
        await _seed(db_session, "-nos", ig_id="IGWNOS")
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "id": "IGWNOS",
                    "changes": [
                        {
                            "field": "comments",
                            "value": {
                                "id": "NOSCMT",
                                "media": {"id": "NOSMED"},
                            },
                        }
                    ],
                }
            ],
        }
        resp = await client.post("/webhooks/instagram", json=payload)
        assert resp.status_code == 200
        row = (
            await db_session.exec(
                select(InstagramComment).where(
                    InstagramComment.ig_comment_id == "NOSCMT"
                )
            )
        ).first()
        assert row is not None
    finally:
        settings.meta_verify_webhook_signature = original
