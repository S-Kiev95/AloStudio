"""Integration tests for the publications API (multi-network publishing)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.publishing.models import Publication, PublicationTarget
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app
from app.workers import publishing as publishing_worker

pytestmark = pytest.mark.integration

IMAGE = {"type": "image", "url": "https://cdn.example.com/a.jpg"}


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
def enqueued(monkeypatch) -> list[int]:
    """Record publish-now enqueues instead of touching Redis."""
    calls: list[int] = []

    async def _fake(publication_id: int) -> None:
        calls.append(publication_id)

    monkeypatch.setattr(publishing_worker, "enqueue_publication", _fake)
    return calls


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@pub.example.com",
            account_name=f"PUB{suffix}",
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


async def _seed_agent(db_session, account_id: int, suffix: str):
    other = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@pub.example.com",
            account_name=f"PUBAGENT{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=account_id,
            user_id=other.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=other.user.tokens, uid=other.user.uid
    )
    other.user.tokens = new_tokens
    db_session.add(other.user)
    await db_session.flush()
    return headers.as_response_headers()


async def _inbox(db_session, account, *, kind: str, suffix: str):
    params = {
        "facebook": {
            "page_id": f"PAGE{suffix}",
            "page_access_token": "page-token",
        },
        "instagram": {
            "instagram_id": f"1784{abs(hash(suffix)) % 10_000_000}",
            "access_token": "ig-token",
        },
        "api": {},
    }[kind]
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=account,
            name=f"{kind.title()} {suffix}",
            channel_type=kind,
            channel_params=params,
        ),
    ).perform()
    return result.inbox


def _future(hours: int = 2) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


async def test_requires_auth(client):
    r = await client.get("/api/v1/accounts/1/publications")
    assert r.status_code == 401


async def test_channels_lists_only_publishable_inboxes(client, db_session):
    owner, h = await _seed_admin(db_session, "-ch")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="ch")
    ig = await _inbox(db_session, owner.account, kind="instagram", suffix="ch")
    await _inbox(db_session, owner.account, kind="api", suffix="ch")

    r = await client.get(
        f"/api/v1/accounts/{owner.account.id}/publications/channels", headers=h
    )
    assert r.status_code == 200, r.text
    channels = {c["inbox_id"]: c["network"] for c in r.json()}
    assert channels == {fb.id: "facebook_page", ig.id: "instagram"}


async def test_create_scheduled_waits_for_the_scheduler(client, db_session, enqueued):
    owner, h = await _seed_admin(db_session, "-sched")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="sched")
    ig = await _inbox(db_session, owner.account, kind="instagram", suffix="sched")

    r = await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications",
        headers=h,
        json={
            "content": "Promo de primavera",
            "media": [IMAGE],
            "scheduled_for": _future(),
            "targets": [
                {"inbox_id": fb.id},
                {"inbox_id": ig.id, "settings": {"post_type": "feed"}},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "scheduled"
    assert {t["channel"]["network"] for t in body["targets"]} == {
        "facebook_page",
        "instagram",
    }
    assert all(t["state"] == "pending" for t in body["targets"])
    assert body["created_by_id"] == owner.user.id
    assert enqueued == []


async def test_create_without_date_is_published_now(client, db_session, enqueued):
    owner, h = await _seed_admin(db_session, "-now")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="now")

    r = await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications",
        headers=h,
        json={"content": "Ya", "targets": [{"inbox_id": fb.id}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "publishing"
    assert enqueued == [r.json()["id"]]


async def test_draft_is_never_enqueued(client, db_session, enqueued):
    owner, h = await _seed_admin(db_session, "-draft")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="draft")

    r = await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications",
        headers=h,
        json={"content": "Idea", "draft": True, "targets": [{"inbox_id": fb.id}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "draft"
    assert enqueued == []


async def test_rejects_bad_channels(client, db_session, enqueued):
    owner, h = await _seed_admin(db_session, "-bad")
    other, _ = await _seed_admin(db_session, "-bad-other")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="bad")
    api = await _inbox(db_session, owner.account, kind="api", suffix="bad")
    foreign = await _inbox(db_session, other.account, kind="facebook", suffix="badf")
    url = f"/api/v1/accounts/{owner.account.id}/publications"

    for targets in (
        [{"inbox_id": foreign.id}],
        [{"inbox_id": api.id}],
        [{"inbox_id": fb.id}, {"inbox_id": fb.id}],
    ):
        r = await client.post(
            url, headers=h, json={"content": "x", "targets": targets}
        )
        assert r.status_code == 422, (targets, r.text)
    assert enqueued == []


async def test_adapter_validation_errors_name_the_channel(client, db_session):
    owner, h = await _seed_admin(db_session, "-val")
    ig = await _inbox(db_session, owner.account, kind="instagram", suffix="val")

    r = await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications",
        headers=h,
        json={
            "content": "Sin foto",
            "scheduled_for": _future(),
            "targets": [{"inbox_id": ig.id}],
        },
    )
    assert r.status_code == 422
    errors = r.json()["errors"]
    assert any(ig.name in e and "imagen o un video" in e for e in errors)


async def test_rejects_past_dates_and_bad_media(client, db_session):
    owner, h = await _seed_admin(db_session, "-past")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="past")
    url = f"/api/v1/accounts/{owner.account.id}/publications"

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    r = await client.post(
        url,
        headers=h,
        json={"content": "x", "scheduled_for": past, "targets": [{"inbox_id": fb.id}]},
    )
    assert r.status_code == 422

    r = await client.post(
        url,
        headers=h,
        json={
            "content": "x",
            "media": [{"type": "gif", "url": "https://x/y.gif"}],
            "targets": [{"inbox_id": fb.id}],
        },
    )
    assert r.status_code == 422


async def test_list_filters_by_date_state_and_channel(client, db_session, enqueued):
    owner, h = await _seed_admin(db_session, "-list")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="list")
    ig = await _inbox(db_session, owner.account, kind="instagram", suffix="list")
    url = f"/api/v1/accounts/{owner.account.id}/publications"

    soon = (await client.post(
        url, headers=h,
        json={"content": "pronto", "scheduled_for": _future(2), "targets": [{"inbox_id": fb.id}]},
    )).json()
    later = (await client.post(
        url, headers=h,
        json={
            "content": "despues",
            "media": [IMAGE],
            "scheduled_for": _future(72),
            "targets": [{"inbox_id": ig.id}],
        },
    )).json()

    window_to = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
    r = await client.get(url, headers=h, params={"to": window_to})
    assert [p["id"] for p in r.json()] == [soon["id"]]

    r = await client.get(url, headers=h, params={"inbox_id": ig.id})
    assert [p["id"] for p in r.json()] == [later["id"]]

    r = await client.get(url, headers=h, params={"state": "scheduled"})
    assert [p["id"] for p in r.json()] == [soon["id"], later["id"]]

    r = await client.get(url, headers=h, params={"state": "nope"})
    assert r.status_code == 422


async def test_edit_and_delete_only_before_publishing(client, db_session, enqueued):
    owner, h = await _seed_admin(db_session, "-edit")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="edit")
    url = f"/api/v1/accounts/{owner.account.id}/publications"

    created = (await client.post(
        url, headers=h,
        json={"content": "v1", "scheduled_for": _future(), "targets": [{"inbox_id": fb.id}]},
    )).json()
    r = await client.patch(f"{url}/{created['id']}", headers=h, json={"content": "v2"})
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "v2"
    assert r.json()["state"] == "scheduled"

    # Editing only the text of one whose date just passed is fine; the
    # future-date check applies to new dates.
    publication = await db_session.get(Publication, created["id"])
    publication.scheduled_for = datetime.now(UTC) - timedelta(minutes=10)
    db_session.add(publication)
    await db_session.flush()
    r = await client.patch(f"{url}/{created['id']}", headers=h, json={"content": "v2b"})
    assert r.status_code == 200, r.text

    publication = await db_session.get(Publication, created["id"])
    publication.state = "published"
    db_session.add(publication)
    await db_session.flush()

    r = await client.patch(f"{url}/{created['id']}", headers=h, json={"content": "v3"})
    assert r.status_code == 422
    r = await client.delete(f"{url}/{created['id']}", headers=h)
    assert r.status_code == 422

    other = (await client.post(
        url, headers=h,
        json={"content": "borrar", "scheduled_for": _future(), "targets": [{"inbox_id": fb.id}]},
    )).json()
    r = await client.delete(f"{url}/{other['id']}", headers=h)
    assert r.status_code == 200
    assert await db_session.get(Publication, other["id"]) is None


async def test_agent_reads_but_only_admins_publish(client, db_session, enqueued):
    """Same rule as Instagram publishing: posts go out under the brand."""
    owner, _ = await _seed_admin(db_session, "-agent")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="agent")
    agent_h = await _seed_agent(db_session, owner.account.id, "-agent")
    url = f"/api/v1/accounts/{owner.account.id}/publications"

    r = await client.get(url, headers=agent_h)
    assert r.status_code == 200
    r = await client.post(
        url,
        headers=agent_h,
        json={"content": "desde agente", "scheduled_for": _future(), "targets": [{"inbox_id": fb.id}]},
    )
    assert r.status_code == 401


async def test_retry_requeues_only_failed_targets(client, db_session, enqueued):
    owner, h = await _seed_admin(db_session, "-retry")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="retry")
    ig = await _inbox(db_session, owner.account, kind="instagram", suffix="retry")
    url = f"/api/v1/accounts/{owner.account.id}/publications"

    created = (await client.post(
        url, headers=h,
        json={
            "content": "x",
            "media": [IMAGE],
            "scheduled_for": _future(),
            "targets": [{"inbox_id": fb.id}, {"inbox_id": ig.id}],
        },
    )).json()
    r = await client.post(f"{url}/{created['id']}/retry", headers=h)
    assert r.status_code == 422  # nothing failed yet

    publication = await db_session.get(Publication, created["id"])
    publication.state = "partially_published"
    db_session.add(publication)
    targets = (await db_session.exec(
        select(PublicationTarget).where(PublicationTarget.publication_id == created["id"])
    )).all()
    for target in targets:
        target.state = "published" if target.inbox_id == fb.id else "failed"
        target.error_message = None if target.inbox_id == fb.id else "boom"
        db_session.add(target)
    await db_session.flush()

    r = await client.post(f"{url}/{created['id']}/retry", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "publishing"
    states = {t["channel"]["inbox_id"]: t["state"] for t in body["targets"]}
    assert states == {fb.id: "published", ig.id: "pending"}
    assert enqueued == [created["id"]]


async def test_other_account_publication_is_404(client, db_session, enqueued):
    owner, h = await _seed_admin(db_session, "-iso")
    other, other_h = await _seed_admin(db_session, "-iso-other")
    fb = await _inbox(db_session, owner.account, kind="facebook", suffix="iso")

    created = (await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications",
        headers=h,
        json={"content": "x", "scheduled_for": _future(), "targets": [{"inbox_id": fb.id}]},
    )).json()
    r = await client.get(
        f"/api/v1/accounts/{other.account.id}/publications/{created['id']}",
        headers=other_h,
    )
    assert r.status_code == 404
