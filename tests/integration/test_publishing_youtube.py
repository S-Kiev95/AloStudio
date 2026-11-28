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

from app.core.auth.devise_token_auth import create_new_auth_token
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
    # Without Analytics (403), the basic figures still come from the Data API.
    respx.get("https://youtubeanalytics.googleapis.com/v2/reports").mock(
        return_value=httpx.Response(403, json={"error": {"code": 403}})
    )
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


async def _headers(db_session, owner) -> dict[str, str]:
    headers, new_tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return headers.as_response_headers()


def _thread(thread_id: str, text: str, replies: list[dict] | None = None) -> dict:
    return {
        "id": thread_id,
        "snippet": {
            "topLevelComment": {
                "id": thread_id,
                "snippet": {
                    "authorDisplayName": "Ana",
                    "authorProfileImageUrl": "https://pic/ana",
                    "textOriginal": text,
                    "textDisplay": f"<b>{text}</b>",
                    "publishedAt": "2026-11-26T18:00:00Z",
                    "likeCount": 2,
                },
            }
        },
        "replies": {"comments": replies or []},
    }


def _reply(reply_id: str, text: str, author: str = "Canal CTC") -> dict:
    return {
        "id": reply_id,
        "snippet": {
            "authorDisplayName": author,
            "textOriginal": text,
            "publishedAt": "2026-11-26T18:05:00Z",
        },
    }


@respx.mock
async def test_reads_the_comments_of_a_published_video(client, db_session):
    owner = await _seed(db_session, "-com")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel)
    target.external_id = "VID1"
    await db_session.flush()
    route = respx.get(f"{API}/commentThreads").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    _thread(
                        "T1",
                        "¿Cuándo empieza?",
                        [_reply("R2", "Segunda"), _reply("R1", "El lunes")],
                    )
                ]
            },
        )
    )

    r = await client.get(
        f"/api/v1/accounts/{owner.account.id}/publications/{publication.id}/targets/{target.id}/comments",
        headers=await _headers(db_session, owner),
    )

    assert r.status_code == 200, r.text
    (comment,) = r.json()["comments"]
    assert (comment["id"], comment["author"], comment["text"], comment["like_count"]) == (
        "T1",
        "Ana",
        "¿Cuándo empieza?",
        2,
    )
    # Replies read oldest first.
    assert [x["text"] for x in comment["replies"]] == ["El lunes", "Segunda"]
    params = route.calls[0].request.url.params
    assert (params["videoId"], params["order"]) == ("VID1", "time")


@respx.mock
async def test_replies_to_a_comment_as_the_channel(client, db_session):
    owner = await _seed(db_session, "-rep")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel)
    target.external_id = "VID1"
    await db_session.flush()
    route = respx.post(f"{API}/comments").mock(
        return_value=httpx.Response(200, json=_reply("R9", "¡Gracias!"))
    )

    r = await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications/{publication.id}/targets/{target.id}/comments/T1/replies",
        headers=await _headers(db_session, owner),
        json={"text": "  ¡Gracias!  "},
    )

    assert r.status_code == 200, r.text
    assert r.json()["comments"][0]["text"] == "¡Gracias!"
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"snippet": {"parentId": "T1", "textOriginal": "¡Gracias!"}}


@respx.mock
async def test_comment_failures_come_back_in_spanish(client, db_session):
    owner = await _seed(db_session, "-cerr")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel)
    base = f"/api/v1/accounts/{owner.account.id}/publications/{publication.id}/targets/{target.id}/comments"
    headers = await _headers(db_session, owner)

    # Not published yet.
    r = await client.get(base, headers=headers)
    assert r.status_code == 422

    target.external_id = "VID1"
    await db_session.flush()
    respx.get(f"{API}/commentThreads").mock(
        return_value=httpx.Response(
            403,
            json={
                "error": {
                    "code": 403,
                    "status": "PERMISSION_DENIED",
                    "details": [{"reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}],
                }
            },
        )
    )
    r = await client.get(base, headers=headers)
    assert r.status_code == 502
    assert "volvé a conectar" in r.json()["message"]

    r = await client.post(f"{base}/T1/replies", headers=headers, json={"text": "  "})
    assert r.status_code == 502
    assert r.json()["message"] == "Escribí la respuesta."


async def test_publications_say_which_targets_have_comments(client, db_session):
    owner = await _seed(db_session, "-flag")
    channel = await _channel(db_session, owner.account)
    publication, _target_row = await _target(db_session, owner.account, channel)

    r = await client.get(
        f"/api/v1/accounts/{owner.account.id}/publications/{publication.id}",
        headers=await _headers(db_session, owner),
    )

    assert r.status_code == 200, r.text
    assert r.json()["targets"][0]["supports_comments"] is True


async def _image_asset(db_session, account_id: int):
    from app.domains.media_library.models import MediaAsset

    asset = MediaAsset(
        account_id=account_id,
        kind="image",
        key="a/miniatura.jpg",
        filename="miniatura.jpg",
        content_type="image/jpeg",
        size_bytes=1000,
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


@respx.mock
async def test_uploads_with_tags_category_thumbnail_and_playlist(db_session):
    owner = await _seed(db_session, "-extra")
    channel = await _channel(db_session, owner.account)
    asset = await _image_asset(db_session, owner.account.id)
    settings = {
        **CHOICES,
        "tags": ["curso", "inglés A1"],
        "category_id": "27",
        "playlist_id": "PL1",
        "thumbnail_media_id": asset.id,
    }
    publication, target = await _target(db_session, owner.account, channel, settings=settings)
    start, _ = _mock_upload()
    respx.get(url__regex=r".*/public/media\?key=a%2Fminiatura\.jpg.*").mock(
        return_value=httpx.Response(
            200, content=b"\xff\xd8jpg", headers={"content-type": "image/jpeg"}
        )
    )
    thumb = respx.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    playlist = respx.post(f"{API}/playlistItems").mock(
        return_value=httpx.Response(200, json={"id": "PI1"})
    )

    result = await YouTubeAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert result.extra == {}
    snippet = json.loads(start.calls[0].request.content)["snippet"]
    assert (snippet["tags"], snippet["categoryId"]) == (["curso", "inglés A1"], "27")
    assert thumb.calls[0].request.url.params["videoId"] == "VID1"
    assert thumb.calls[0].request.headers["Content-Type"] == "image/jpeg"
    item = json.loads(playlist.calls[0].request.content)["snippet"]
    assert item == {"playlistId": "PL1", "resourceId": {"kind": "youtube#video", "videoId": "VID1"}}


@respx.mock
async def test_thumbnail_and_playlist_problems_are_warnings(db_session):
    owner = await _seed(db_session, "-warn")
    channel = await _channel(db_session, owner.account)
    asset = await _image_asset(db_session, owner.account.id)
    settings = {**CHOICES, "playlist_id": "PLX", "thumbnail_media_id": asset.id}
    publication, target = await _target(db_session, owner.account, channel, settings=settings)
    _mock_upload()
    respx.get(url__regex=r".*/public/media\?key=a%2Fminiatura\.jpg.*").mock(
        return_value=httpx.Response(
            200, content=b"\xff\xd8jpg", headers={"content-type": "image/jpeg"}
        )
    )
    respx.post("https://www.googleapis.com/upload/youtube/v3/thumbnails/set").mock(
        return_value=httpx.Response(
            403, json={"error": {"code": 403, "errors": [{"reason": "forbidden"}]}}
        )
    )
    respx.post(f"{API}/playlistItems").mock(
        return_value=httpx.Response(
            404, json={"error": {"code": 404, "message": "Playlist not found"}}
        )
    )

    result = await YouTubeAdapter().publish(db_session, publication, target)

    # The video is up: problems after it never fail the post.
    assert result.ok and result.external_id == "VID1"
    warnings = result.extra["warnings"]
    assert "verificado por teléfono" in warnings[0]
    assert warnings[1].startswith("No se pudo agregar a la lista")


async def test_validation_of_tags_and_category(db_session):
    from app.domains.publishing.adapters.youtube import tags_length

    owner = await _seed(db_session, "-tags")
    channel = await _channel(db_session, owner.account)
    publication, target = await _target(db_session, owner.account, channel)
    adapter = YouTubeAdapter()

    assert tags_length(["a b", "cd"]) == 3 + 2 + 2 + 1
    target.settings = {**CHOICES, "tags": ["x" * 300, "y" * 300]}
    assert any("500 caracteres" in p for p in adapter.validate(publication, target))
    target.settings = {**CHOICES, "tags": ["uno, dos"], "category_id": "abc"}
    problems = adapter.validate(publication, target)
    assert any("comas" in p for p in problems)
    assert any("categoría" in p for p in problems)


@respx.mock
async def test_the_editor_reads_playlists_and_categories(db_session):
    owner = await _seed(db_session, "-ci")
    channel = await _channel(db_session, owner.account)
    respx.get(f"{API}/playlists").mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": "PL1", "snippet": {"title": "Cursos"}}]}
        )
    )
    respx.get(f"{API}/videoCategories").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": "27", "snippet": {"title": "Educación", "assignable": True}},
                    {"id": "18", "snippet": {"title": "Cortos", "assignable": False}},
                ]
            },
        )
    )

    info = await YouTubeAdapter().compose_info(db_session, channel)

    assert info["can_post"] is True
    assert info["playlists"] == [{"id": "PL1", "title": "Cursos"}]
    assert info["categories"] == [{"id": "27", "title": "Educación"}]


ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"


def _analytics_reply(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    dims = params.get("dimensions")
    if dims == "day":
        return httpx.Response(
            200,
            json={
                "rows": [
                    ["2026-11-20", 40, 12.5, 3, 1, 2, 4, 1],
                    ["2026-11-21", 10, 2, 1, 0, 0, 0, 0],
                ]
            },
        )
    if dims == "day,insightTrafficSourceType":
        return httpx.Response(
            200,
            json={"rows": [["2026-11-20", "YT_SEARCH", 25], ["2026-11-20", "SUGGESTED", 15]]},
        )
    if dims == "ageGroup,gender":
        return httpx.Response(
            200,
            json={
                "rows": [
                    ["age18-24", "female", 30.0],
                    ["age18-24", "male", 20.0],
                    ["age25-34", "male", 50.0],
                ]
            },
        )
    if dims == "country":
        return httpx.Response(200, json={"rows": [["UY", 30], ["AR", 10]]})
    # Per video.
    assert params["filters"] == "video==VID1"
    return httpx.Response(200, json={"rows": [[90.0, 135.5, 4]]})


@respx.mock
async def test_channel_figures_from_youtube_analytics(db_session):
    from datetime import date as _date

    owner = await _seed(db_session, "-yta")
    channel = await _channel(db_session, owner.account)
    respx.get(f"{API}/channels").mock(
        return_value=httpx.Response(
            200, json={"items": [{"statistics": {"subscriberCount": "345"}}]}
        )
    )
    route = respx.get(ANALYTICS).mock(side_effect=_analytics_reply)

    result = await YouTubeAdapter().fetch_channel_metrics(
        db_session, channel, days=[_date(2026, 11, 20), _date(2026, 11, 21)]
    )

    assert result is not None and result.ok
    assert result.metrics == {"followers": 345}
    day = result.daily[_date(2026, 11, 20)]
    assert day["views"] == 40 and day["watch_time_ms"] == 750_000
    assert (day["likes"], day["comments"], day["shares"], day["interactions"]) == (3, 1, 2, 6)
    assert (day["follows"], day["unfollows"]) == (4, 1)
    assert day["views_by_traffic_source"] == {"YT_SEARCH": 25, "SUGGESTED": 15}
    engaged = result.audience["engaged"]
    assert engaged["age"] == {"18-24": 50.0, "25-34": 50.0}
    assert engaged["gender"] == {"F": 30.0, "M": 70.0}
    assert engaged["country"] == {"UY": 30, "AR": 10}
    assert route.calls[0].request.url.params["ids"] == "channel==MINE"


@respx.mock
async def test_video_figures_add_watch_time(db_session):
    owner = await _seed(db_session, "-ytv")
    channel = await _channel(db_session, owner.account)
    _publication, target = await _target(db_session, owner.account, channel)
    target.external_id = "VID1"
    respx.get(f"{API}/videos").mock(
        return_value=httpx.Response(200, json={"items": [{"statistics": {"viewCount": "120"}}]})
    )
    respx.get(ANALYTICS).mock(side_effect=_analytics_reply)

    post = await YouTubeAdapter().fetch_post_metrics(db_session, target)

    assert post is not None and post.ok
    assert post.metrics == {
        "views": 120,
        "watch_time_ms": 5_400_000,
        "avg_watch_time_ms": 135_500,
        "shares": 4,
    }


@respx.mock
async def test_without_analytics_the_basic_figures_still_go_out(db_session):
    from datetime import date as _date

    owner = await _seed(db_session, "-ytn")
    channel = await _channel(db_session, owner.account)
    respx.get(f"{API}/channels").mock(
        return_value=httpx.Response(200, json={"items": [{"statistics": {"subscriberCount": "7"}}]})
    )
    # A channel connected before the Analytics scope was asked for.
    respx.get(ANALYTICS).mock(return_value=httpx.Response(403, json={"error": {"code": 403}}))

    result = await YouTubeAdapter().fetch_channel_metrics(
        db_session, channel, days=[_date(2026, 11, 20)]
    )

    assert result is not None and result.ok
    assert (result.metrics, result.daily, result.audience) == ({"followers": 7}, {}, {})
