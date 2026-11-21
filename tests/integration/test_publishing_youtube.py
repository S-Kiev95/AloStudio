"""YouTube: connecting with the installation's Google client, uploading a
video with a resumable upload, renewing the hour-long token, errors in
Spanish, validation and figures. Google is mocked with respx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.config import get_settings
from app.core.db import get_session
from app.core.oauth_state import sign_oauth_state
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.publishing import connections
from app.domains.publishing import service as svc
from app.domains.publishing.adapters.youtube import YouTubeAdapter
from app.domains.publishing.models import PublishingChannel
from app.domains.teams import models as _teams  # noqa: F401
from app.main import app

pytestmark = pytest.mark.integration

API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
TOKEN = "https://oauth2.googleapis.com/token"
SESSION_URL = "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=UP1"
VIDEO = {
    "type": "video",
    "url": "https://app.example.com/public/media?key=a%2Fclip.mp4&exp=1&sig=s",
}
PHOTO = {
    "type": "image",
    "url": "https://app.example.com/public/media?key=a%2Ffoto.jpg&exp=1&sig=s",
}
CHOICES = {"title": "Mi primer video", "privacy_status": "unlisted"}
CLIP = b"\x00\x00\x00\x18ftypmp42" + b"x" * 3000


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
def google_config():
    settings = get_settings()
    names = ("google_client_id", "google_client_secret", "publishing_oauth_redirect_uri")
    orig = {name: getattr(settings, name) for name in names}
    settings.google_client_id = "GID"
    settings.google_client_secret = "GSECRET"
    settings.publishing_oauth_redirect_uri = (
        "https://app.example.com/api/v1/publishing/oauth/callback"
    )
    try:
        yield settings
    finally:
        for name, value in orig.items():
            setattr(settings, name, value)


async def _seed(db_session, suffix: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@youtube.example.com",
            account_name=f"YT{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _channel(
    db_session, account, *, access_expires_in=timedelta(hours=1)
) -> PublishingChannel:
    channel = PublishingChannel(
        account_id=account.id,
        network="youtube",
        name="Canal CTC",
        external_id="UC123",
        credentials={
            "access_token": "YTTOKEN",
            "refresh_token": "YTREFRESH",
            "access_expires_at": (datetime.now(UTC) + access_expires_in).isoformat(),
        },
    )
    db_session.add(channel)
    await db_session.flush()
    return channel


async def _target(
    db_session, account, channel, *, media=(VIDEO,), settings=CHOICES, content="Descripción"
):
    publication = await svc.create_publication(
        db_session,
        account_id=account.id,
        payload={
            "content": content,
            "media": list(media),
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"channel_id": channel.id, "settings": settings}],
        },
    )
    (target,) = (await svc.targets_by_publication(db_session, publication_ids=[publication.id]))[
        publication.id
    ]
    return publication, target


def _mock_upload(video_id: str = "VID1"):
    respx.get(VIDEO["url"]).mock(
        return_value=httpx.Response(200, content=CLIP, headers={"content-type": "video/mp4"})
    )
    start = respx.post(UPLOAD).mock(
        return_value=httpx.Response(200, headers={"location": SESSION_URL})
    )
    put = respx.put(SESSION_URL).mock(return_value=httpx.Response(200, json={"id": video_id}))
    return start, put


@respx.mock
async def test_connect_through_the_callback(client, db_session, google_config):
    owner = await _seed(db_session, "-cb")
    url = connections.start_connection(owner.account.id, "youtube")
    query = parse_qs(urlparse(url).query)
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert query["client_id"] == ["GID"]
    assert query["access_type"] == ["offline"] and query["prompt"] == ["consent"]
    assert "https://www.googleapis.com/auth/youtube.upload" in query["scope"][0]

    token = respx.post(TOKEN).mock(
        return_value=httpx.Response(
            200, json={"access_token": "YTTOKEN", "expires_in": 3599, "refresh_token": "YTREFRESH"}
        )
    )
    respx.get(f"{API}/channels").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "UC123",
                        "snippet": {
                            "title": "Canal CTC",
                            "customUrl": "@ctcsalto",
                            "thumbnails": {"default": {"url": "https://pic"}},
                        },
                    }
                ]
            },
        )
    )
    state = sign_oauth_state(owner.account.id, flow="publishing:youtube")

    r = await client.get("/api/v1/publishing/oauth/callback", params={"code": "C", "state": state})

    assert r.status_code == 303
    assert parse_qs(urlparse(r.headers["location"]).query)["connected"] == ["youtube"]
    sent = parse_qs(token.calls[0].request.content.decode())
    assert sent["client_secret"] == ["GSECRET"] and sent["grant_type"] == ["authorization_code"]
    channel = (
        await db_session.exec(
            select(PublishingChannel).where(PublishingChannel.account_id == owner.account.id)
        )
    ).one()
    assert (channel.external_id, channel.name, channel.username) == (
        "UC123",
        "Canal CTC",
        "ctcsalto",
    )
    assert channel.credentials["refresh_token"] == "YTREFRESH"


@respx.mock
async def test_connecting_an_account_without_a_channel_says_so(client, db_session, google_config):
    owner = await _seed(db_session, "-nochan")
    respx.post(TOKEN).mock(
        return_value=httpx.Response(
            200, json={"access_token": "T", "expires_in": 3599, "refresh_token": "R"}
        )
    )
    respx.get(f"{API}/channels").mock(return_value=httpx.Response(200, json={"items": []}))
    state = sign_oauth_state(owner.account.id, flow="publishing:youtube")

    r = await client.get("/api/v1/publishing/oauth/callback", params={"code": "C", "state": state})

    assert r.status_code == 303
    assert (
        "no tiene un canal" in parse_qs(urlparse(r.headers["location"]).query)["connect_error"][0]
    )


@respx.mock
async def test_uploads_the_video_with_the_choices(db_session):
    owner = await _seed(db_session, "-up")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel)
    start, put = _mock_upload()

    result = await YouTubeAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert (result.external_id, result.permalink) == (
        "VID1",
        "https://www.youtube.com/watch?v=VID1",
    )
    request = start.calls[0].request
    assert request.headers["Authorization"] == "Bearer YTTOKEN"
    assert request.headers["X-Upload-Content-Length"] == str(len(CLIP))
    assert request.headers["X-Upload-Content-Type"] == "video/mp4"
    body = json.loads(request.content)
    assert body["snippet"]["title"] == "Mi primer video"
    assert body["snippet"]["description"] == "Descripción"
    assert body["status"] == {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False}
    assert put.calls[0].request.content == CLIP


@respx.mock
async def test_renews_the_access_token_before_uploading(db_session, google_config):
    owner = await _seed(db_session, "-ren")
    channel = await _channel(db_session, owner.account, access_expires_in=timedelta(minutes=-1))
    publication, target = await _target(db_session, owner.account, channel)
    refresh = respx.post(TOKEN).mock(
        return_value=httpx.Response(200, json={"access_token": "NEWTOKEN", "expires_in": 3599})
    )
    start, _ = _mock_upload()

    result = await YouTubeAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert parse_qs(refresh.calls[0].request.content.decode())["refresh_token"] == ["YTREFRESH"]
    assert start.calls[0].request.headers["Authorization"] == "Bearer NEWTOKEN"
    await db_session.refresh(channel)
    # Google keeps the same refresh token.
    assert channel.credentials["refresh_token"] == "YTREFRESH"
    assert channel.credentials["access_token"] == "NEWTOKEN"


@respx.mock
async def test_failures_come_back_in_spanish(db_session, google_config):
    owner = await _seed(db_session, "-err")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel)
    start, _ = _mock_upload()
    start.mock(
        return_value=httpx.Response(
            403, json={"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}]}}
        )
    )

    result = await YouTubeAdapter().publish(db_session, publication, target)
    assert not result.ok and result.retryable
    assert "cuota" in result.error_message

    start.mock(return_value=httpx.Response(401, json={"error": {"code": 401}}))
    result = await YouTubeAdapter().publish(db_session, publication, target)
    assert not result.ok and not result.retryable
    await db_session.refresh(channel)
    assert channel.status == "reconnect"


async def test_validation_follows_youtubes_rules(db_session):
    owner = await _seed(db_session, "-val")
    channel = await _channel(db_session, owner.account)
    adapter = YouTubeAdapter()

    publication, target = await _target(db_session, owner.account, channel)
    assert adapter.validate(publication, target) == []

    # The editor checks before saving; here the same target is changed in place.
    publication.media = [PHOTO]
    assert adapter.validate(publication, target) == ["YouTube necesita un solo video, sin fotos."]

    publication.media = [VIDEO]
    publication.content = "<b>"
    target.settings = {"title": "x" * 101}
    problems = adapter.validate(publication, target)
    assert any("100 caracteres" in p for p in problems)
    assert any("descripción" in p and "<" in p for p in problems)

    publication.content = "Hola"
    target.settings = {}
    assert adapter.validate(publication, target) == ["Poné el título del video de YouTube."]


@respx.mock
async def test_reads_the_figures(db_session):
    owner = await _seed(db_session, "-met")
    channel = await _channel(db_session, owner.account)
    _publication, target = await _target(db_session, owner.account, channel)
    target.external_id = "VID1"
    respx.get(f"{API}/videos").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"statistics": {"viewCount": "120", "likeCount": "8", "commentCount": "2"}}
                ]
            },
        )
    )
    respx.get(f"{API}/channels").mock(
        return_value=httpx.Response(
            200, json={"items": [{"statistics": {"subscriberCount": "345"}}]}
        )
    )

    post = await YouTubeAdapter().fetch_post_metrics(db_session, target)
    account = await YouTubeAdapter().fetch_channel_metrics(db_session, channel, days=[])

    assert post is not None and post.metrics == {"views": 120, "likes": 8, "comments": 2}
    assert account is not None and account.metrics == {"followers": 345}
