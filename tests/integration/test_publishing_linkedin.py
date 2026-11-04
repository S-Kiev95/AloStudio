"""LinkedIn (member profile): connecting, publishing text and images, the
little-format escaping and token expiry. LinkedIn is mocked with respx."""

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
from app.domains.publishing.adapters.base import ChannelConnectionError
from app.domains.publishing.adapters.linkedin import LinkedInAdapter, escape_little
from app.domains.publishing.models import PublishingChannel
from app.domains.teams import models as _teams  # noqa: F401
from app.main import app

pytestmark = pytest.mark.integration

REST = "https://api.linkedin.com/rest"
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
def linkedin_config():
    settings = get_settings()
    orig = (
        settings.linkedin_client_id,
        settings.linkedin_client_secret,
        settings.publishing_oauth_redirect_uri,
        settings.app_base_url,
    )
    settings.linkedin_client_id = "LIID"
    settings.linkedin_client_secret = "LISECRET"
    settings.publishing_oauth_redirect_uri = "https://app.example.com/api/v1/publishing/oauth/callback"
    settings.app_base_url = "https://app.example.com"
    try:
        yield settings
    finally:
        (
            settings.linkedin_client_id,
            settings.linkedin_client_secret,
            settings.publishing_oauth_redirect_uri,
            settings.app_base_url,
        ) = orig


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@linkedin.example.com",
            account_name=f"LI{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    return owner


async def _channel(db_session, account, **fields) -> PublishingChannel:
    channel = PublishingChannel(
        account_id=account.id,
        network="linkedin",
        name="Ezequiel Viera",
        external_id="abc123",
        credentials={"access_token": "LITOKEN"},
        token_expires_at=datetime.now(UTC) + timedelta(days=50),
        **fields,
    )
    db_session.add(channel)
    await db_session.flush()
    return channel


async def _target(db_session, account, channel, *, content="Hola LinkedIn", media=None):
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


def test_little_format_escaping():
    assert escape_little("Hola (mundo) @juan *ok* #salto # suelto a_b") == (
        "Hola \\(mundo\\) \\@juan \\*ok\\* #salto \\# suelto a\\_b"
    )


@respx.mock
async def test_connect_through_the_callback(client, db_session, linkedin_config):
    owner = await _seed(db_session, "-cb")
    url = connections.start_connection(owner.account.id, "linkedin")
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == ["openid profile w_member_social"]
    assert query["client_id"] == ["LIID"]

    token = respx.post("https://www.linkedin.com/oauth/v2/accessToken").mock(
        return_value=httpx.Response(200, json={"access_token": "LITOKEN", "expires_in": 5184000})
    )
    respx.get("https://api.linkedin.com/v2/userinfo").mock(
        return_value=httpx.Response(
            200, json={"sub": "abc123", "name": "Ezequiel Viera", "picture": "https://pic"}
        )
    )
    state = sign_oauth_state(owner.account.id, flow="publishing:linkedin")

    r = await client.get("/api/v1/publishing/oauth/callback", params={"code": "C", "state": state})

    assert r.status_code == 303
    assert parse_qs(urlparse(r.headers["location"]).query)["connected"] == ["linkedin"]
    assert parse_qs(token.calls[0].request.content.decode())["client_secret"] == ["LISECRET"]
    channel = (
        await db_session.exec(
            select(PublishingChannel).where(PublishingChannel.account_id == owner.account.id)
        )
    ).one()
    assert (channel.external_id, channel.name, channel.credentials) == (
        "abc123",
        "Ezequiel Viera",
        {"access_token": "LITOKEN"},
    )


@respx.mock
async def test_publishes_text_with_escaping(db_session):
    owner = await _seed(db_session, "-text")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel, content="Oferta (hoy) #salto")
    route = respx.post(f"{REST}/posts").mock(
        return_value=httpx.Response(201, headers={"x-restli-id": "urn:li:share:777"})
    )

    result = await LinkedInAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert result.external_id == "urn:li:share:777"
    assert result.permalink == "https://www.linkedin.com/feed/update/urn:li:share:777/"
    request = route.calls[0].request
    assert request.headers["X-Restli-Protocol-Version"] == "2.0.0"
    assert request.headers["Linkedin-Version"] == get_settings().linkedin_api_version
    body = json.loads(request.content)
    assert body["author"] == "urn:li:person:abc123"
    assert body["commentary"] == "Oferta \\(hoy\\) #salto"
    assert "content" not in body


@respx.mock
async def test_publishes_one_or_several_images(db_session):
    owner = await _seed(db_session, "-img")
    channel = await _channel(db_session, owner.account)
    counter = iter(range(1, 10))

    def _init(request):
        n = next(counter)
        return httpx.Response(
            200,
            json={"value": {"uploadUrl": f"https://upload.linkedin.com/{n}", "image": f"urn:li:image:I{n}"}},
        )

    respx.post(f"{REST}/images").mock(side_effect=_init)
    respx.get(IMAGE["url"]).mock(return_value=httpx.Response(200, content=b"JPEGDATA"))
    uploads = respx.put(url__regex=r"https://upload\.linkedin\.com/\d+").mock(
        return_value=httpx.Response(201)
    )
    posts = respx.post(f"{REST}/posts").mock(
        return_value=httpx.Response(201, headers={"x-restli-id": "urn:li:share:9"})
    )
    adapter = LinkedInAdapter()

    publication, target = await _target(db_session, owner.account, channel, media=[IMAGE])
    assert (await adapter.publish(db_session, publication, target)).ok
    assert json.loads(posts.calls[0].request.content)["content"] == {"media": {"id": "urn:li:image:I1"}}
    assert uploads.calls[0].request.content == b"JPEGDATA"

    publication, target = await _target(db_session, owner.account, channel, media=[IMAGE, IMAGE])
    assert (await adapter.publish(db_session, publication, target)).ok
    assert json.loads(posts.calls[1].request.content)["content"] == {
        "multiImage": {"images": [{"id": "urn:li:image:I2"}, {"id": "urn:li:image:I3"}]}
    }


@respx.mock
async def test_publishes_a_video_by_parts_once_processed(db_session, monkeypatch):
    monkeypatch.setattr("app.domains.publishing.adapters.linkedin.VIDEO_POLL_SECONDS", 0)
    owner = await _seed(db_session, "-vid")
    channel = await _channel(db_session, owner.account)
    video_url = "https://cdn.example.com/a.mp4"
    content = b"a" * 6 + b"b" * 4
    respx.get(video_url).mock(
        return_value=httpx.Response(
            200, content=content, headers={"content-length": str(len(content))}
        )
    )
    urn = "urn:li:video:V1"

    def videos(request: httpx.Request) -> httpx.Response:
        if request.url.params["action"] == "initializeUpload":
            return httpx.Response(
                200,
                json={
                    "value": {
                        "video": urn,
                        "uploadToken": "TOK",
                        "uploadInstructions": [
                            {"uploadUrl": "https://up.example.com/1", "firstByte": 0, "lastByte": 5},
                            {"uploadUrl": "https://up.example.com/2", "firstByte": 6, "lastByte": 9},
                        ],
                    }
                },
            )
        return httpx.Response(200)

    action = respx.post(f"{REST}/videos").mock(side_effect=videos)
    part1 = respx.put("https://up.example.com/1").mock(
        return_value=httpx.Response(200, headers={"etag": '"E1"'})
    )
    part2 = respx.put("https://up.example.com/2").mock(
        return_value=httpx.Response(200, headers={"etag": "E2"})
    )
    status = respx.get(f"{REST}/videos/urn%3Ali%3Avideo%3AV1").mock(
        side_effect=[
            httpx.Response(200, json={"status": "PROCESSING"}),
            httpx.Response(200, json={"status": "AVAILABLE"}),
        ]
    )
    post = respx.post(f"{REST}/posts").mock(
        return_value=httpx.Response(201, headers={"x-restli-id": "urn:li:share:9"})
    )
    publication, target = await _target(
        db_session,
        owner.account,
        channel,
        content="Mi video\ncon detalle",
        media=[{"type": "video", "url": video_url}],
    )
    assert LinkedInAdapter().validate(publication, target) == []

    result = await LinkedInAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert part1.calls[0].request.content == b"a" * 6
    assert part2.calls[0].request.content == b"b" * 4
    assert json.loads(action.calls[0].request.content)["initializeUploadRequest"]["fileSizeBytes"] == 10
    assert json.loads(action.calls[1].request.content)["finalizeUploadRequest"] == {
        "video": urn,
        "uploadToken": "TOK",
        "uploadedPartIds": ["E1", "E2"],
    }
    assert status.call_count == 2
    assert json.loads(post.calls[0].request.content)["content"] == {
        "media": {"title": "Mi video", "id": urn}
    }


@respx.mock
async def test_a_video_linkedin_cannot_process_is_not_posted(db_session):
    owner = await _seed(db_session, "-vidf")
    channel = await _channel(db_session, owner.account)
    video_url = "https://cdn.example.com/a.mp4"
    respx.get(video_url).mock(
        return_value=httpx.Response(200, content=b"abc", headers={"content-length": "3"})
    )
    respx.post(f"{REST}/videos").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "value": {
                        "video": "urn:li:video:V2",
                        "uploadInstructions": [
                            {"uploadUrl": "https://up.example.com/1", "firstByte": 0, "lastByte": 2}
                        ],
                    }
                },
            ),
            httpx.Response(200),
        ]
    )
    respx.put("https://up.example.com/1").mock(
        return_value=httpx.Response(200, headers={"etag": "E1"})
    )
    respx.get(f"{REST}/videos/urn%3Ali%3Avideo%3AV2").mock(
        return_value=httpx.Response(
            200, json={"status": "PROCESSING_FAILED", "processingFailureReason": "formato"}
        )
    )
    post = respx.post(f"{REST}/posts")
    publication, target = await _target(
        db_session, owner.account, channel, media=[{"type": "video", "url": video_url}]
    )

    result = await LinkedInAdapter().publish(db_session, publication, target)

    assert not result.ok and "formato" in result.error_message
    assert post.call_count == 0


@respx.mock
async def test_expired_token_flags_reconnect_and_a_video_goes_alone(db_session):
    owner = await _seed(db_session, "-exp")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel)
    respx.post(f"{REST}/posts").mock(return_value=httpx.Response(401, json={"message": "Expired"}))

    result = await LinkedInAdapter().publish(db_session, publication, target)

    assert not result.ok
    await db_session.refresh(channel)
    assert channel.status == "reconnect"

    publication.media = [{"type": "video", "url": "https://cdn.example.com/a.mp4"}, IMAGE]
    assert "1 video" in LinkedInAdapter().validate(publication, target)[0]
    publication.media = []
    publication.content = "x" * 3001
    assert "3000" in LinkedInAdapter().validate(publication, target)[0]


async def test_no_refresh_token_means_reconnect_only_after_expiry(db_session):
    owner = await _seed(db_session, "-ref")
    adapter = LinkedInAdapter()
    soon = await _channel(db_session, owner.account)
    soon.token_expires_at = datetime.now(UTC) + timedelta(days=3)
    assert await adapter.refresh_credentials(soon) is None

    soon.token_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    with pytest.raises(ChannelConnectionError):
        await adapter.refresh_credentials(soon)
