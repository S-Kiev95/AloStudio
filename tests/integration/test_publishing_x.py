"""X: connecting with OAuth 2.0 + PKCE, renewing the 2-hour token, and
publishing with media. X is mocked with respx."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.db import get_session
from app.domains.publishing import connections
from app.domains.publishing.adapters.x import (
    API_BASE,
    SEGMENT_BYTES,
    TOKEN_URL,
    XAdapter,
    x_length,
)
from app.domains.publishing.models import PublishingChannel
from app.main import app
from tests.integration.test_publishing_telegram_discord import (
    IMAGE,
    VIDEO,
    _channel,
    _seed,
    _target,
)

pytestmark = pytest.mark.integration

REDIRECT = "https://app.example.com/api/v1/publishing/oauth/callback"
TWEETS = f"{API_BASE}/tweets"


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
def x_config():
    settings = get_settings()
    names = ("x_client_id", "x_client_secret", "publishing_oauth_redirect_uri")
    orig = {name: getattr(settings, name) for name in names}
    settings.x_client_id = "XID"
    settings.x_client_secret = "XSECRET"
    settings.publishing_oauth_redirect_uri = REDIRECT
    try:
        yield settings
    finally:
        for name, value in orig.items():
            setattr(settings, name, value)


async def _x(db_session, account, *, expires_in=timedelta(hours=1)):
    return await _channel(
        db_session,
        account,
        "x",
        {
            "access_token": "ACCESS",
            "refresh_token": "REFRESH",
            "access_expires_at": (datetime.now(UTC) + expires_in).isoformat(),
        },
        external_id="77",
        name="Zeek",
        username="zeek",
    )


def _mock_upload(media_id: str, *, content: bytes, content_type: str, url: str, **finalize):
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=content,
            headers={"content-type": content_type, "content-length": str(len(content))},
        )
    )
    init = respx.post(f"{API_BASE}/media/upload/initialize").mock(
        return_value=httpx.Response(200, json={"data": {"id": media_id}})
    )
    append = respx.post(f"{API_BASE}/media/upload/{media_id}/append").mock(
        return_value=httpx.Response(204)
    )
    respx.post(f"{API_BASE}/media/upload/{media_id}/finalize").mock(
        return_value=httpx.Response(200, json={"data": {"id": media_id, **finalize}})
    )
    return init, append


def test_counts_like_x():
    assert x_length("Hola") == 4
    assert x_length("Mirá https://ejemplo.com/una/ruta/muy/larga/de/verdad") == 5 + 23
    assert x_length("🚀") == 2


@respx.mock
async def test_connect_through_the_callback(client, db_session, x_config):
    owner, _h = await _seed(db_session, "-xc")
    url = connections.start_connection(owner.account.id, "x")
    assert url.startswith("https://x.com/i/oauth2/authorize?")
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["XID"]
    assert query["code_challenge_method"] == ["S256"]
    assert "media.write" in query["scope"][0] and "offline.access" in query["scope"][0]

    token = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "ACCESS", "refresh_token": "REFRESH", "expires_in": 7200}
        )
    )
    respx.get(f"{API_BASE}/users/me").mock(
        return_value=httpx.Response(
            200, json={"data": {"id": "77", "name": "Zeek", "username": "zeek"}}
        )
    )
    r = await client.get(
        "/api/v1/publishing/oauth/callback",
        params={"code": "CODE", "state": query["state"][0]},
    )
    assert r.status_code == 303, r.text
    assert "connected=x" in r.headers["location"]

    # The verifier sent is the one the challenge at the start was made from.
    request = token.calls[0].request
    assert request.headers["authorization"] == "Basic " + base64.b64encode(b"XID:XSECRET").decode()
    verifier = parse_qs(request.content.decode())["code_verifier"][0]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert challenge.decode().rstrip("=") == query["code_challenge"][0]


@respx.mock
async def test_publishes_text_and_links_the_post(db_session):
    owner, _h = await _seed(db_session, "-xp")
    channel = await _x(db_session, owner.account)
    route = respx.post(TWEETS).mock(
        return_value=httpx.Response(201, json={"data": {"id": "999", "text": "Hola"}})
    )
    publication, target = await _target(db_session, owner.account, channel)

    result = await XAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert result.permalink == "https://x.com/zeek/status/999"
    assert json.loads(route.calls[0].request.content) == {"text": "Hola"}
    assert route.calls[0].request.headers["authorization"] == "Bearer ACCESS"


@respx.mock
async def test_uploads_an_image_first(db_session):
    owner, _h = await _seed(db_session, "-xi")
    channel = await _x(db_session, owner.account)
    init, append = _mock_upload(
        "M1", content=b"img", content_type="image/jpeg", url=IMAGE["url"]
    )
    route = respx.post(TWEETS).mock(
        return_value=httpx.Response(201, json={"data": {"id": "1", "text": ""}})
    )
    publication, target = await _target(db_session, owner.account, channel, media=[IMAGE])

    result = await XAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert json.loads(init.calls[0].request.content) == {
        "media_type": "image/jpeg",
        "total_bytes": 3,
        "media_category": "tweet_image",
    }
    assert append.call_count == 1
    assert json.loads(route.calls[0].request.content)["media"] == {"media_ids": ["M1"]}


@respx.mock
async def test_a_video_goes_by_segments_and_waits_for_processing(db_session):
    owner, _h = await _seed(db_session, "-xv")
    channel = await _x(db_session, owner.account)
    init, append = _mock_upload(
        "M2",
        content=b"v" * (SEGMENT_BYTES + 1),
        content_type="video/mp4",
        url=VIDEO["url"],
        processing_info={"state": "pending", "check_after_secs": 0},
    )
    status = respx.get(f"{API_BASE}/media/upload").mock(
        return_value=httpx.Response(200, json={"data": {"processing_info": {"state": "succeeded"}}})
    )
    respx.post(TWEETS).mock(
        return_value=httpx.Response(201, json={"data": {"id": "2", "text": ""}})
    )
    publication, target = await _target(db_session, owner.account, channel, media=[VIDEO])

    result = await XAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert json.loads(init.calls[0].request.content)["media_category"] == "tweet_video"
    assert append.call_count == 2
    assert status.call_count == 1


@respx.mock
async def test_renews_the_access_token_before_publishing(db_session, x_config):
    owner, _h = await _seed(db_session, "-xr")
    channel = await _x(db_session, owner.account, expires_in=timedelta(minutes=-1))
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "NEW", "refresh_token": "NEWR", "expires_in": 7200}
        )
    )
    route = respx.post(TWEETS).mock(
        return_value=httpx.Response(201, json={"data": {"id": "3", "text": "Hola"}})
    )
    publication, target = await _target(db_session, owner.account, channel)

    result = await XAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert route.calls[0].request.headers["authorization"] == "Bearer NEW"
    stored = await db_session.get(PublishingChannel, channel.id)
    assert stored.credentials["refresh_token"] == "NEWR"


@respx.mock
@pytest.mark.parametrize(
    ("status", "body", "retryable", "expected"),
    [
        (402, {"title": "CreditsDepleted"}, False, "sin crédito"),
        (403, {"detail": "duplicate content"}, False, "duplicate content"),
        (429, {"title": "Too Many Requests"}, True, "se reintenta"),
        (503, {}, True, "se reintenta"),
    ],
)
async def test_failures_come_back_in_spanish(db_session, status, body, retryable, expected):
    owner, _h = await _seed(db_session, f"-xf{status}")
    channel = await _x(db_session, owner.account)
    respx.post(TWEETS).mock(return_value=httpx.Response(status, json=body))
    publication, target = await _target(db_session, owner.account, channel)

    result = await XAdapter().publish(db_session, publication, target)

    assert not result.ok and result.retryable is retryable
    assert expected in result.error_message


@respx.mock
async def test_a_revoked_token_flags_reconnect(db_session):
    owner, _h = await _seed(db_session, "-xg")
    channel = await _x(db_session, owner.account)
    respx.post(TWEETS).mock(return_value=httpx.Response(401, json={"title": "Unauthorized"}))
    publication, target = await _target(db_session, owner.account, channel)

    result = await XAdapter().publish(db_session, publication, target)

    assert not result.ok
    await db_session.refresh(channel)
    assert channel.status == "reconnect"


async def test_validation_follows_xs_rules(db_session):
    owner, _h = await _seed(db_session, "-xval")
    channel = await _x(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel)
    adapter = XAdapter()
    assert adapter.validate(publication, target) == []

    publication.content = "x" * 281
    assert "280" in adapter.validate(publication, target)[0]

    publication.content = "Hola"
    publication.media = [IMAGE] * 5
    assert "4 imágenes" in adapter.validate(publication, target)[0]
    publication.media = [IMAGE, VIDEO]
    assert "1 video" in adapter.validate(publication, target)[0]
