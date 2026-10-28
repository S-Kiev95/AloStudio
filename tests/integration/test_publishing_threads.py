"""Threads: connecting an account (generic connect flow + callback),
publishing every kind of post, figures, token renewal and disconnecting.
Threads' API is mocked with respx."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.core.oauth_state import sign_oauth_state, verify_oauth_state
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.publishing import connections
from app.domains.publishing import service as svc
from app.domains.publishing.adapters import threads as threads_adapter
from app.domains.publishing.adapters.threads import ThreadsAdapter, threads_length
from app.domains.publishing.models import PublishingChannel
from app.domains.teams import models as _teams  # noqa: F401
from app.main import app
from tests.integration._publishing import channel_of

pytestmark = pytest.mark.integration

GRAPH = "https://graph.threads.net"
API = f"{GRAPH}/v1.0"
USER = "7781"
IMAGE = {"type": "image", "url": "https://cdn.example.com/a.jpg"}
VIDEO = {"type": "video", "url": "https://cdn.example.com/a.mp4"}


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
def threads_config():
    settings = get_settings()
    orig = (
        settings.threads_app_id,
        settings.threads_app_secret,
        settings.publishing_oauth_redirect_uri,
        settings.app_base_url,
    )
    settings.threads_app_id = "THAPP"
    settings.threads_app_secret = "THSECRET"
    settings.publishing_oauth_redirect_uri = (
        "https://app.example.com/api/v1/publishing/oauth/callback"
    )
    settings.app_base_url = "https://app.example.com"
    try:
        yield settings
    finally:
        (
            settings.threads_app_id,
            settings.threads_app_secret,
            settings.publishing_oauth_redirect_uri,
            settings.app_base_url,
        ) = orig


@pytest.fixture(autouse=True)
def _no_polling_wait(monkeypatch):
    monkeypatch.setattr(threads_adapter, "POLL_SECONDS", 0.0)


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@threads.example.com",
            account_name=f"THR{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _threads_channel(
    db_session, account, *, external_id: str = USER, token: str = "LONG", expires_in_days: int = 50
) -> PublishingChannel:
    channel = PublishingChannel(
        account_id=account.id,
        network="threads",
        name="Mi Threads",
        username="mithreads",
        external_id=external_id,
        credentials={"access_token": token},
        token_expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
    )
    db_session.add(channel)
    await db_session.flush()
    return channel


async def _target(db_session, account, channel, *, content="Hola Threads", media=None):
    publication = await svc.create_publication(
        db_session,
        account_id=account.id,
        payload={
            "content": content,
            "media": media or [],
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"channel_id": channel.id}],
        },
    )
    (target,) = (
        await svc.targets_by_publication(db_session, publication_ids=[publication.id])
    )[publication.id]
    return publication, target


def _mock_connect():
    respx.post(f"{GRAPH}/oauth/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "SHORT", "user_id": USER})
    )
    respx.get(f"{GRAPH}/access_token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "LONG", "token_type": "bearer", "expires_in": 5183944}
        )
    )
    return respx.get(f"{API}/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": USER,
                "username": "mithreads",
                "name": "Mi Threads",
                "threads_profile_picture_url": "https://cdn.threads/pic.jpg",
            },
        )
    )


# ---------------------------------------------------------------------------
# Connecting
# ---------------------------------------------------------------------------
async def test_networks_and_connect_need_the_settings(client, db_session):
    owner, h = await _seed(db_session, "-cfg")
    base = f"/api/v1/accounts/{owner.account.id}/publications"
    settings = get_settings()
    orig = settings.threads_app_id
    settings.threads_app_id = ""
    try:
        r = await client.get(f"{base}/networks", headers=h)
        assert {"network": "threads", "label": "Threads", "configured": False} in r.json()
        r = await client.post(f"{base}/channels/connect/threads", headers=h)
        assert r.status_code == 422
        assert "THREADS_APP_ID" in r.json()["message"]
    finally:
        settings.threads_app_id = orig

    r = await client.post(f"{base}/channels/connect/instagram", headers=h)
    assert r.status_code == 404


async def test_connect_returns_the_authorization_window(client, db_session, threads_config):
    owner, h = await _seed(db_session, "-start")

    r = await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications/channels/connect/threads",
        headers=h,
    )

    assert r.status_code == 200, r.text
    url = urlparse(r.json()["authorize_url"])
    query = parse_qs(url.query)
    assert url.netloc == "threads.net" and url.path == "/oauth/authorize"
    assert query["client_id"] == ["THAPP"]
    assert query["redirect_uri"] == [threads_config.publishing_oauth_redirect_uri]
    assert query["scope"] == ["threads_basic,threads_content_publish,threads_manage_insights"]
    assert query["response_type"] == ["code"]
    assert connections.network_of_state(verify_oauth_state(query["state"][0])) == "threads"


@respx.mock
async def test_callback_creates_then_refreshes_the_channel(client, db_session, threads_config):
    owner, h = await _seed(db_session, "-cb")
    state = sign_oauth_state(owner.account.id, flow="publishing:threads")
    me = _mock_connect()

    r = await client.get(
        "/api/v1/publishing/oauth/callback", params={"code": "CODE", "state": state}
    )

    assert r.status_code == 303
    location = urlparse(r.headers["location"])
    assert location.path == f"/accounts/{owner.account.id}/publications"
    assert parse_qs(location.query)["connected"] == ["threads"]
    channel = (
        await db_session.exec(
            select(PublishingChannel).where(PublishingChannel.account_id == owner.account.id)
        )
    ).one()
    assert (channel.network, channel.external_id, channel.username) == ("threads", USER, "mithreads")
    assert channel.credentials == {"access_token": "LONG"}
    assert channel.token_expires_at > datetime.now(UTC) + timedelta(days=59)
    assert me.calls[0].request.url.params["access_token"] == "LONG"

    # Connecting the same profile again (after a reconnect warning) reuses it.
    channel.status = "reconnect"
    channel.status_message = "venció"
    db_session.add(channel)
    await db_session.flush()
    r = await client.get(
        "/api/v1/publishing/oauth/callback", params={"code": "CODE2", "state": state}
    )
    assert r.status_code == 303
    rows = (
        await db_session.exec(
            select(PublishingChannel)
            .where(PublishingChannel.account_id == owner.account.id)
            .execution_options(populate_existing=True)
        )
    ).all()
    assert [(c.id, c.status, c.status_message) for c in rows] == [(channel.id, "active", None)]

    listed = await client.get(
        f"/api/v1/accounts/{owner.account.id}/publications/channels", headers=h
    )
    (presented,) = listed.json()
    assert presented["network"] == "threads" and presented["inbox_id"] is None
    assert "credentials" not in presented


@respx.mock
async def test_callback_failures_go_back_with_a_message(client, db_session, threads_config):
    owner, _h = await _seed(db_session, "-cbfail")
    state = sign_oauth_state(owner.account.id, flow="publishing:threads")

    r = await client.get(
        "/api/v1/publishing/oauth/callback",
        params={"error": "access_denied", "state": state},
    )
    assert r.status_code == 303
    assert "connect_error" in parse_qs(urlparse(r.headers["location"]).query)

    respx.post(f"{GRAPH}/oauth/access_token").mock(
        return_value=httpx.Response(
            400,
            json={"error_type": "OAuthException", "code": 400, "error_message": "code used"},
        )
    )
    r = await client.get(
        "/api/v1/publishing/oauth/callback", params={"code": "OLD", "state": state}
    )
    message = parse_qs(urlparse(r.headers["location"]).query)["connect_error"][0]
    assert "code used" in message

    r = await client.get(
        "/api/v1/publishing/oauth/callback", params={"code": "X", "state": "forged.sig"}
    )
    assert r.status_code == 400
    # A state signed for another flow (Instagram's) isn't accepted here.
    r = await client.get(
        "/api/v1/publishing/oauth/callback",
        params={"code": "X", "state": sign_oauth_state(owner.account.id, flow="instagram")},
    )
    assert r.status_code == 400


async def test_disconnecting(client, db_session):
    owner, h = await _seed(db_session, "-del")
    channel = await _threads_channel(db_session, owner.account)
    page = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Pagina",
                channel_type="facebook",
                channel_params={"page_id": "PG-del", "page_access_token": "t"},
            ),
        ).perform()
    ).inbox
    page_channel = await channel_of(db_session, page)
    base = f"/api/v1/accounts/{owner.account.id}/publications/channels"

    r = await client.delete(f"{base}/{page_channel.id}", headers=h)
    assert r.status_code == 422
    r = await client.delete(f"{base}/{channel.id}", headers=h)
    assert r.status_code == 200
    assert await db_session.get(PublishingChannel, channel.id) is None
    r = await client.delete(f"{base}/{channel.id}", headers=h)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------
def _mock_publish(container_statuses=("FINISHED",)):
    created = respx.post(f"{API}/{USER}/threads").mock(
        side_effect=[httpx.Response(200, json={"id": f"C{i}"}) for i in range(1, 25)]
    )
    statuses = iter(container_statuses)
    last = {"status": container_statuses[-1]}

    def _status(request):
        return httpx.Response(200, json={"status": next(statuses, last["status"])})

    status = respx.get(url__regex=rf"{API}/C\d+\?").mock(side_effect=_status)
    published = respx.post(f"{API}/{USER}/threads_publish").mock(
        return_value=httpx.Response(200, json={"id": "M1"})
    )
    respx.get(url__regex=rf"{API}/M1\?").mock(
        return_value=httpx.Response(200, json={"permalink": "https://threads.net/@mithreads/post/1"})
    )
    return created, status, published


def _form(call) -> dict[str, list[str]]:
    return parse_qs(call.request.content.decode())


@respx.mock
async def test_publishes_text(db_session):
    owner, _h = await _seed(db_session, "-text")
    channel = await _threads_channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel)
    created, _status, published = _mock_publish()

    result = await ThreadsAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert (result.external_id, result.permalink) == ("M1", "https://threads.net/@mithreads/post/1")
    assert _form(created.calls[0]) == {
        "media_type": ["TEXT"],
        "text": ["Hola Threads"],
        "access_token": ["LONG"],
    }
    assert _form(published.calls[0])["creation_id"] == ["C1"]


@respx.mock
async def test_publishes_a_video_after_it_is_processed(db_session):
    owner, _h = await _seed(db_session, "-video")
    channel = await _threads_channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel, media=[VIDEO])
    created, status, _published = _mock_publish(("IN_PROGRESS", "IN_PROGRESS", "FINISHED"))

    result = await ThreadsAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    form = _form(created.calls[0])
    assert form["media_type"] == ["VIDEO"] and form["video_url"] == [VIDEO["url"]]
    assert status.call_count == 3


@respx.mock
async def test_publishes_a_carousel(db_session):
    owner, _h = await _seed(db_session, "-carousel")
    channel = await _threads_channel(db_session, owner.account)
    publication, target = await _target(
        db_session, owner.account, channel, media=[IMAGE, VIDEO, IMAGE]
    )
    created, _status, published = _mock_publish()

    result = await ThreadsAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    forms = [_form(call) for call in created.calls]
    assert [f["media_type"][0] for f in forms] == ["IMAGE", "VIDEO", "IMAGE", "CAROUSEL"]
    assert all(f["is_carousel_item"] == ["true"] for f in forms[:3])
    assert forms[3]["children"] == ["C1,C2,C3"] and forms[3]["text"] == ["Hola Threads"]
    assert _form(published.calls[0])["creation_id"] == ["C4"]


@respx.mock
async def test_a_failed_container_or_expired_token(db_session):
    owner, _h = await _seed(db_session, "-fail")
    channel = await _threads_channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel, media=[IMAGE])
    _mock_publish(("ERROR",))

    result = await ThreadsAdapter().publish(db_session, publication, target)
    assert not result.ok and "no pudo procesar" in result.error_message

    respx.post(f"{API}/{USER}/threads").mock(
        return_value=httpx.Response(
            400, json={"error": {"code": 190, "message": "Error validating access token"}}
        )
    )
    result = await ThreadsAdapter().publish(db_session, publication, target)
    assert not result.ok and not result.retryable
    await db_session.refresh(channel)
    assert channel.status == "reconnect" and "Volvé a conectar" in channel.status_message


async def test_validation(db_session):
    owner, _h = await _seed(db_session, "-val")
    channel = await _threads_channel(db_session, owner.account)
    adapter = ThreadsAdapter()

    publication, target = await _target(db_session, owner.account, channel)
    publication.content = "a" * 500
    assert adapter.validate(publication, target) == []
    publication.content = "a" * 497 + "😀"
    assert threads_length(publication.content) == 501
    assert "500" in adapter.validate(publication, target)[0]
    # Accents count as one character, not as their UTF-8 bytes.
    assert threads_length("canción") == 7
    publication.content = ""
    publication.media = [IMAGE] * 21
    assert "20" in adapter.validate(publication, target)[0]
    publication.media = []
    assert adapter.validate(publication, target) == [
        "Threads necesita texto o al menos una imagen o video."
    ]


# ---------------------------------------------------------------------------
# Figures and tokens
# ---------------------------------------------------------------------------
@respx.mock
async def test_post_and_channel_figures(db_session):
    owner, _h = await _seed(db_session, "-stats")
    channel = await _threads_channel(db_session, owner.account)
    _publication, target = await _target(db_session, owner.account, channel)
    target.external_id = "M9"
    respx.get(url__regex=rf"{API}/M9/insights").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"name": "views", "period": "lifetime", "values": [{"value": 120}]},
                    {"name": "likes", "period": "lifetime", "values": [{"value": 10}]},
                    {"name": "replies", "period": "lifetime", "values": [{"value": 3}]},
                    {"name": "reposts", "period": "lifetime", "values": [{"value": 2}]},
                    {"name": "quotes", "period": "lifetime", "values": [{"value": 1}]},
                ]
            },
        )
    )

    def _user_insights(request):
        if request.url.params["metric"] == "followers_count":
            return httpx.Response(
                200, json={"data": [{"name": "followers_count", "total_value": {"value": 88}}]}
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {"name": "views", "period": "day", "values": [{"value": 40}]},
                    {"name": "likes", "period": "day", "total_value": {"value": 5}},
                    {"name": "replies", "period": "day", "total_value": {"value": 1}},
                ]
            },
        )

    respx.get(url__regex=rf"{API}/{USER}/threads_insights").mock(side_effect=_user_insights)
    adapter = ThreadsAdapter()

    post = await adapter.fetch_post_metrics(db_session, target)
    day = date(2026, 10, 27)
    account = await adapter.fetch_channel_metrics(db_session, channel, days=[day])

    assert post.metrics == {
        "likes": 10,
        "comments": 3,
        "shares": 3,
        "interactions": 16,
        "views": 120,
    }
    assert account.metrics == {"followers": 88}
    assert account.daily == {day: {"views": 40, "interactions": 6}}


@respx.mock
async def test_tokens_close_to_expiring_are_renewed(db_session):
    owner, _h = await _seed(db_session, "-renew")
    soon = await _threads_channel(db_session, owner.account, expires_in_days=3)
    later = await _threads_channel(db_session, owner.account, external_id="7782")
    revoked = await _threads_channel(
        db_session, owner.account, external_id="7783", token="DEAD", expires_in_days=1
    )

    def _refresh(request):
        if request.url.params["access_token"] == "DEAD":
            return httpx.Response(
                400, json={"error": {"code": 190, "message": "Session has expired"}}
            )
        return httpx.Response(
            200, json={"access_token": "RENEWED", "token_type": "bearer", "expires_in": 5183944}
        )

    route = respx.get(f"{GRAPH}/refresh_access_token").mock(side_effect=_refresh)

    renewed = await connections.refresh_expiring_channels(db_session)

    assert renewed == 1
    assert route.call_count == 2
    for row in (soon, later, revoked):
        await db_session.refresh(row)
    assert soon.credentials == {"access_token": "RENEWED"}
    assert soon.token_expires_at > datetime.now(UTC) + timedelta(days=59)
    assert later.credentials == {"access_token": "LONG"}
    assert revoked.status == "reconnect"
