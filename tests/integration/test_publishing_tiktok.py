"""TikTok: connecting, publishing a video or photos with the creator's
choices, renewing the 2-hour token, the editor's account info and the URL
verification file. TikTok is mocked with respx."""

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

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.core.oauth_state import sign_oauth_state
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.publishing import connections
from app.domains.publishing import service as svc
from app.domains.publishing.adapters import tiktok
from app.domains.publishing.adapters.tiktok import TikTokAdapter
from app.domains.publishing.models import PublishingChannel
from app.domains.teams import models as _teams  # noqa: F401
from app.main import app

pytestmark = pytest.mark.integration

API = "https://open.tiktokapis.com/v2"
VIDEO = {"type": "video", "url": "https://app.example.com/public/media?key=a%2Fclip.mp4&exp=1&sig=s"}
PHOTO = {"type": "image", "url": "https://app.example.com/public/media?key=a%2Ffoto.jpg&exp=1&sig=s"}
PNG = {"type": "image", "url": "https://app.example.com/public/media?key=a%2Ffoto.png&exp=1&sig=s"}
CHOICES = {"privacy_level": "SELF_ONLY", "allow_comment": True}
CREATOR = {
    "creator_nickname": "Ezequiel",
    "creator_username": "skiev",
    "creator_avatar_url": "https://pic",
    "privacy_level_options": ["FOLLOWER_OF_CREATOR", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
    "comment_disabled": False,
    "duet_disabled": True,
    "stitch_disabled": True,
    "max_video_post_duration_sec": 600,
}


def _ok(data: dict) -> httpx.Response:
    return httpx.Response(200, json={"data": data, "error": {"code": "ok", "message": ""}})


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setattr(tiktok, "POLL_SECONDS", 0.0)


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
def tiktok_config():
    settings = get_settings()
    names = (
        "tiktok_client_key",
        "tiktok_client_secret",
        "tiktok_verification_file",
        "tiktok_verification_content",
        "publishing_oauth_redirect_uri",
        "app_base_url",
    )
    orig = {name: getattr(settings, name) for name in names}
    settings.tiktok_client_key = "TTKEY"
    settings.tiktok_client_secret = "TTSECRET"
    settings.publishing_oauth_redirect_uri = "https://app.example.com/api/v1/publishing/oauth/callback"
    settings.app_base_url = "https://app.example.com"
    try:
        yield settings
    finally:
        for name, value in orig.items():
            setattr(settings, name, value)


async def _seed(db_session, suffix: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@tiktok.example.com",
            account_name=f"TT{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _channel(db_session, account, *, access_expires_in=timedelta(hours=1)) -> PublishingChannel:
    channel = PublishingChannel(
        account_id=account.id,
        network="tiktok",
        name="Ezequiel",
        external_id="OPENID",
        credentials={
            "access_token": "TTTOKEN",
            "refresh_token": "TTREFRESH",
            "open_id": "OPENID",
            "access_expires_at": (datetime.now(UTC) + access_expires_in).isoformat(),
        },
        token_expires_at=datetime.now(UTC) + timedelta(days=170),
    )
    db_session.add(channel)
    await db_session.flush()
    return channel


async def _target(db_session, account, channel, *, media, settings=CHOICES, content="Hola #tiktok"):
    publication = await svc.create_publication(
        db_session,
        account_id=account.id,
        payload={
            "content": content,
            "media": media,
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"channel_id": channel.id, "settings": settings}],
        },
    )
    (target,) = (
        await svc.targets_by_publication(db_session, publication_ids=[publication.id])
    )[publication.id]
    return publication, target


@respx.mock
async def test_connect_through_the_callback(client, db_session, tiktok_config):
    owner = await _seed(db_session, "-cb")
    url = connections.start_connection(owner.account.id, "tiktok")
    query = parse_qs(urlparse(url).query)
    assert url.startswith("https://www.tiktok.com/v2/auth/authorize/")
    assert query["scope"] == ["user.info.basic,video.publish"]
    assert query["client_key"] == ["TTKEY"]

    token = respx.post(f"{API}/oauth/token/").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "TTTOKEN",
                "expires_in": 7200,
                "refresh_token": "TTREFRESH",
                "refresh_expires_in": 15552000,
                "open_id": "OPENID",
                "scope": "user.info.basic,video.publish",
                "token_type": "Bearer",
            },
        )
    )
    respx.get(f"{API}/user/info/").mock(
        return_value=_ok({"user": {"open_id": "OPENID", "display_name": "Ezequiel", "avatar_url": "https://pic"}})
    )
    state = sign_oauth_state(owner.account.id, flow="publishing:tiktok")

    r = await client.get("/api/v1/publishing/oauth/callback", params={"code": "C", "state": state})

    assert r.status_code == 303
    assert parse_qs(urlparse(r.headers["location"]).query)["connected"] == ["tiktok"]
    sent = parse_qs(token.calls[0].request.content.decode())
    assert sent["client_secret"] == ["TTSECRET"] and sent["grant_type"] == ["authorization_code"]
    channel = (
        await db_session.exec(
            select(PublishingChannel).where(PublishingChannel.account_id == owner.account.id)
        )
    ).one()
    assert (channel.external_id, channel.name) == ("OPENID", "Ezequiel")
    assert channel.credentials["refresh_token"] == "TTREFRESH"
    assert "access_expires_at" in channel.credentials
    assert channel.token_expires_at > datetime.now(UTC) + timedelta(days=170)


@respx.mock
async def test_publishes_a_video_with_the_creators_choices(db_session):
    owner = await _seed(db_session, "-vid")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel, media=[VIDEO])
    respx.post(f"{API}/post/publish/creator_info/query/").mock(return_value=_ok(CREATOR))
    init = respx.post(f"{API}/post/publish/video/init/").mock(return_value=_ok({"publish_id": "PUB1"}))
    statuses = iter(
        [_ok({"status": "PROCESSING_DOWNLOAD"}), _ok({"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": []})]
    )
    respx.post(f"{API}/post/publish/status/fetch/").mock(side_effect=lambda _r: next(statuses))

    result = await TikTokAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    # Private posts have no public id or link.
    assert (result.external_id, result.permalink) == ("PUB1", None)
    body = json.loads(init.calls[0].request.content)
    assert body["source_info"] == {"source": "PULL_FROM_URL", "video_url": VIDEO["url"]}
    assert body["post_info"] == {
        "privacy_level": "SELF_ONLY",
        "title": "Hola #tiktok",
        "disable_comment": False,
        # Off unless chosen, and always off when the account disables them.
        "disable_duet": True,
        "disable_stitch": True,
        "brand_organic_toggle": False,
        "brand_content_toggle": False,
    }


@respx.mock
async def test_publishes_photos_and_links_a_public_post(db_session):
    owner = await _seed(db_session, "-pho")
    channel = await _channel(db_session, owner.account)
    choices = {"privacy_level": "FOLLOWER_OF_CREATOR", "disclose": True, "brand_organic": True}
    publication, target = await _target(db_session, owner.account, channel, media=[PHOTO, PHOTO], settings=choices)
    respx.post(f"{API}/post/publish/creator_info/query/").mock(return_value=_ok(CREATOR))
    init = respx.post(f"{API}/post/publish/content/init/").mock(return_value=_ok({"publish_id": "PUB2"}))
    respx.post(f"{API}/post/publish/status/fetch/").mock(
        return_value=_ok({"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": [7123]})
    )

    result = await TikTokAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert result.permalink == "https://www.tiktok.com/@skiev/video/7123"
    body = json.loads(init.calls[0].request.content)
    assert (body["post_mode"], body["media_type"]) == ("DIRECT_POST", "PHOTO")
    assert body["source_info"]["photo_images"] == [PHOTO["url"], PHOTO["url"]]
    assert body["post_info"]["description"] == "Hola #tiktok"
    assert body["post_info"]["disable_comment"] is True
    assert body["post_info"]["brand_organic_toggle"] is True


@respx.mock
async def test_renews_the_access_token_before_publishing(db_session, tiktok_config):
    owner = await _seed(db_session, "-ren")
    channel = await _channel(db_session, owner.account, access_expires_in=timedelta(minutes=-1))
    publication, target = await _target(db_session, owner.account, channel, media=[VIDEO])
    refresh = respx.post(f"{API}/oauth/token/").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "NEWTOKEN",
                "expires_in": 7200,
                "refresh_token": "NEWREFRESH",
                "refresh_expires_in": 15552000,
                "open_id": "OPENID",
            },
        )
    )
    info = respx.post(f"{API}/post/publish/creator_info/query/").mock(return_value=_ok(CREATOR))
    respx.post(f"{API}/post/publish/video/init/").mock(return_value=_ok({"publish_id": "PUB3"}))
    respx.post(f"{API}/post/publish/status/fetch/").mock(return_value=_ok({"status": "PUBLISH_COMPLETE"}))

    result = await TikTokAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert parse_qs(refresh.calls[0].request.content.decode())["refresh_token"] == ["TTREFRESH"]
    assert info.calls[0].request.headers["Authorization"] == "Bearer NEWTOKEN"
    await db_session.refresh(channel)
    assert channel.credentials["refresh_token"] == "NEWREFRESH"


@respx.mock
async def test_failures_come_back_in_spanish(db_session):
    owner = await _seed(db_session, "-err")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel, media=[VIDEO])
    respx.post(f"{API}/post/publish/creator_info/query/").mock(return_value=_ok(CREATOR))
    init = respx.post(f"{API}/post/publish/video/init/").mock(
        return_value=httpx.Response(
            403,
            json={"error": {"code": "unaudited_client_can_only_post_to_private_accounts", "message": ""}},
        )
    )

    result = await TikTokAdapter().publish(db_session, publication, target)
    assert not result.ok and not result.retryable
    assert "cuentas privadas" in result.error_message

    init.mock(return_value=_ok({"publish_id": "PUB4"}))
    respx.post(f"{API}/post/publish/status/fetch/").mock(
        return_value=_ok({"status": "FAILED", "fail_reason": "duration_check_failed"})
    )
    result = await TikTokAdapter().publish(db_session, publication, target)
    assert result.error_code == "duration_check_failed"
    assert "más largo" in result.error_message

    respx.post(f"{API}/post/publish/creator_info/query/").mock(
        return_value=httpx.Response(401, json={"error": {"code": "access_token_invalid", "message": ""}})
    )
    result = await TikTokAdapter().publish(db_session, publication, target)
    assert not result.ok
    await db_session.refresh(channel)
    assert channel.status == "reconnect"


async def test_validation_follows_tiktoks_rules(db_session):
    owner = await _seed(db_session, "-val")
    channel = await _channel(db_session, owner.account)
    adapter = TikTokAdapter()
    publication, target = await _target(db_session, owner.account, channel, media=[VIDEO])
    assert adapter.validate(publication, target) == []

    publication.media = []
    assert "video o al menos una foto" in adapter.validate(publication, target)[0]
    publication.media = [VIDEO, PHOTO]
    assert "sin mezclarlos" in adapter.validate(publication, target)[0]
    publication.media = [PNG]
    assert "JPG o WebP" in adapter.validate(publication, target)[0]

    publication.media = [PHOTO]
    target.settings = {}
    assert "quién puede ver" in adapter.validate(publication, target)[0]
    target.settings = {"privacy_level": "SELF_ONLY", "disclose": True}
    assert "promociona" in adapter.validate(publication, target)[0]
    target.settings = {"privacy_level": "SELF_ONLY", "disclose": True, "brand_content": True}
    assert "Solo yo" in adapter.validate(publication, target)[0]


@respx.mock
async def test_the_editor_reads_the_creators_info(client, db_session):
    owner = await _seed(db_session, "-info")
    channel = await _channel(db_session, owner.account)
    respx.post(f"{API}/post/publish/creator_info/query/").mock(return_value=_ok(CREATOR))
    headers, new_tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    r = await client.get(
        f"/api/v1/accounts/{owner.account.id}/publications/channels/{channel.id}/compose_info",
        headers=headers.as_response_headers(),
    )
    assert r.status_code == 200, r.text
    assert r.json()["nickname"] == "Ezequiel"
    assert r.json()["privacy_level_options"] == CREATOR["privacy_level_options"]
    assert r.json()["duet_disabled"] is True


async def test_serves_the_url_verification_file(client, tiktok_config):
    r = await client.get("/public/tiktokAbC123.txt")
    assert r.status_code == 404

    tiktok_config.tiktok_verification_file = "tiktokAbC123.txt"
    tiktok_config.tiktok_verification_content = "tiktok-developers-site-verification=AbC123"
    r = await client.get("/public/tiktokAbC123.txt")
    assert r.status_code == 200
    assert r.text == "tiktok-developers-site-verification=AbC123"
    assert (await client.get("/public/tiktokOtro.txt")).status_code == 404
