"""Plugs: automatic actions on a channel's own posts at N likes (Threads:
reply and repost). Threads is mocked with respx."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.publishing import plugs
from app.domains.publishing import service as svc
from app.domains.publishing.adapters import threads as threads_adapter
from app.domains.publishing.models import PublishingChannel, PublishingPlug, PublishingPlugRun
from app.domains.teams import models as _teams  # noqa: F401
from app.main import app
from tests.integration._publishing import channel_id_of

pytestmark = pytest.mark.integration

API = "https://graph.threads.net/v1.0"
USER = "8801"


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


@pytest.fixture(autouse=True)
def _no_polling_wait(monkeypatch):
    monkeypatch.setattr(threads_adapter, "POLL_SECONDS", 0.0)


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@plugs.example.com",
            account_name=f"PLG{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _threads(db_session, account, external_id: str = USER) -> PublishingChannel:
    channel = PublishingChannel(
        account_id=account.id,
        network="threads",
        name="Mi Threads",
        external_id=external_id,
        credentials={"access_token": "LONG"},
    )
    db_session.add(channel)
    await db_session.flush()
    return channel


async def _post(db_session, account, channel, *, media_id: str, likes: int, days_ago: int = 1):
    publication = await svc.create_publication(
        db_session,
        account_id=account.id,
        payload={
            "content": f"post {media_id}",
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"channel_id": channel.id}],
        },
    )
    (target,) = (
        await svc.targets_by_publication(db_session, publication_ids=[publication.id])
    )[publication.id]
    target.state = "published"
    target.external_id = media_id
    target.published_at = datetime.now(UTC) - timedelta(days=days_ago)
    target.metrics = {"likes": likes}
    db_session.add(target)
    await db_session.flush()
    return target


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
async def test_catalog_and_crud(client, db_session):
    owner, h = await _seed(db_session, "-api")
    channel = await _threads(db_session, owner.account)
    base = f"/api/v1/accounts/{owner.account.id}/publications/plugs"

    catalog = (await client.get(f"{base}/catalog", headers=h)).json()
    (threads,) = [c for c in catalog if c["network"] == "threads"]
    assert [k["kind"] for k in threads["kinds"]] == ["reply_after_likes", "repost_after_likes"]
    assert threads["kinds"][0]["message_max"] == 500

    r = await client.post(
        base,
        headers=h,
        json={"channel_id": channel.id, "kind": "reply_after_likes", "likes_threshold": 50, "message": "¡Gracias! Link: https://x"},
    )
    assert r.status_code == 200, r.text
    created = r.json()
    assert (created["likes_threshold"], created["active"], created["runs"]) == (50, True, [])

    r = await client.patch(f"{base}/{created['id']}", headers=h, json={"likes_threshold": 10, "active": False})
    assert (r.json()["likes_threshold"], r.json()["active"]) == (10, False)
    assert [p["kind"] for p in (await client.get(base, headers=h)).json()] == ["reply_after_likes"]
    assert (await client.delete(f"{base}/{created['id']}", headers=h)).status_code == 200


async def test_invalid_plugs_are_refused(client, db_session):
    owner, h = await _seed(db_session, "-bad")
    other, _ = await _seed(db_session, "-bad2")
    channel = await _threads(db_session, owner.account)
    foreign = await _threads(db_session, other.account, external_id="9902")
    page = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Pagina",
                channel_type="facebook",
                channel_params={"page_id": "PG-plugs", "page_access_token": "t"},
            ),
        ).perform()
    ).inbox
    page_channel = await channel_id_of(db_session, page)
    base = f"/api/v1/accounts/{owner.account.id}/publications/plugs"
    await client.post(base, headers=h, json={"channel_id": channel.id, "kind": "repost_after_likes", "likes_threshold": 5})

    for body in (
        {"channel_id": channel.id, "kind": "reply_after_likes", "likes_threshold": 5},  # no message
        {"channel_id": channel.id, "kind": "reply_after_likes", "likes_threshold": 5, "message": "x" * 501},
        {"channel_id": channel.id, "kind": "repost_after_likes", "likes_threshold": 9},  # duplicate
        {"channel_id": channel.id, "kind": "repost_after_likes", "likes_threshold": 0},
        {"channel_id": channel.id, "kind": "explode", "likes_threshold": 5},
        {"channel_id": page_channel, "kind": "repost_after_likes", "likes_threshold": 5},  # no plugs on pages
        {"channel_id": foreign.id, "kind": "repost_after_likes", "likes_threshold": 5},
    ):
        r = await client.post(base, headers=h, json=body)
        assert r.status_code == 422, (body, r.text)


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------
@respx.mock
async def test_reply_and_repost_fire_once_when_the_threshold_is_reached(db_session):
    owner, _h = await _seed(db_session, "-run")
    channel = await _threads(db_session, owner.account)
    hot = await _post(db_session, owner.account, channel, media_id="M1", likes=12)
    cold = await _post(db_session, owner.account, channel, media_id="M2", likes=3)
    old = await _post(db_session, owner.account, channel, media_id="M3", likes=99, days_ago=45)
    reply = PublishingPlug(
        account_id=owner.account.id, channel_id=channel.id, kind="reply_after_likes",
        likes_threshold=10, message="Gracias por los me gusta",
    )
    repost = PublishingPlug(
        account_id=owner.account.id, channel_id=channel.id, kind="repost_after_likes", likes_threshold=10,
    )
    db_session.add_all([reply, repost])
    await db_session.flush()
    created = respx.post(f"{API}/{USER}/threads").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    respx.get(url__regex=rf"{API}/C1\?").mock(return_value=httpx.Response(200, json={"status": "FINISHED"}))
    respx.post(f"{API}/{USER}/threads_publish").mock(return_value=httpx.Response(200, json={"id": "R1"}))
    reposted = respx.post(f"{API}/M1/repost").mock(return_value=httpx.Response(200, json={"id": "RP1"}))

    assert await plugs.run_due_plugs(db_session) == 2
    assert await plugs.run_due_plugs(db_session) == 0

    form = parse_qs(created.calls[0].request.content.decode())
    assert form["reply_to_id"] == ["M1"] and form["text"] == ["Gracias por los me gusta"]
    assert reposted.call_count == 1
    runs = (await db_session.exec(select(PublishingPlugRun))).all()
    assert {(r.plug_id, r.target_id, r.ok) for r in runs} == {(reply.id, hot.id, True), (repost.id, hot.id, True)}
    assert cold.id not in {r.target_id for r in runs} and old.id not in {r.target_id for r in runs}


@respx.mock
async def test_a_failed_run_is_recorded_and_not_repeated(db_session):
    owner, _h = await _seed(db_session, "-fail")
    channel = await _threads(db_session, owner.account)
    target = await _post(db_session, owner.account, channel, media_id="M9", likes=20)
    plug = PublishingPlug(
        account_id=owner.account.id, channel_id=channel.id, kind="repost_after_likes", likes_threshold=5,
    )
    db_session.add(plug)
    await db_session.flush()
    route = respx.post(f"{API}/M9/repost").mock(
        return_value=httpx.Response(400, json={"error": {"code": 10, "message": "no permission"}})
    )

    assert await plugs.run_due_plugs(db_session) == 1
    assert await plugs.run_due_plugs(db_session) == 0
    assert route.call_count == 1
    (run,) = (await db_session.exec(select(PublishingPlugRun))).all()
    assert (run.target_id, run.ok) == (target.id, False)
    assert "permiso" in run.error_message
