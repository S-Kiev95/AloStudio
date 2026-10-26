"""Facebook Page adapter against a mocked Graph API (respx)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.core.models_registry import import_all_models
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.publishing import service as svc
from app.domains.publishing.adapters.facebook_page import FacebookPageAdapter

import_all_models()

pytestmark = pytest.mark.integration

PAGE_ID = "PAGE123"
IMG_A = {"type": "image", "url": "https://cdn.example.com/a.jpg"}
IMG_B = {"type": "image", "url": "https://cdn.example.com/b.jpg"}
VIDEO = {"type": "video", "url": "https://cdn.example.com/v.mp4"}


def _graph() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_api_version}"


def _graph_video() -> str:
    return f"https://graph-video.facebook.com/{get_settings().meta_graph_api_version}"


def _form(request: httpx.Request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


async def _target(db_session, suffix: str, *, content: str, media: list):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@pubfb.example.com",
            account_name=f"PUBFB{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Pagina",
                channel_type="facebook",
                channel_params={
                    "page_id": PAGE_ID,
                    "page_access_token": "PAGE-TOKEN",
                },
            ),
        ).perform()
    ).inbox
    publication = await svc.create_publication(
        db_session,
        account_id=owner.account.id,
        payload={
            "content": content,
            "media": media,
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"inbox_id": inbox.id}],
        },
    )
    (target,) = (
        await svc.targets_by_publication(db_session, publication_ids=[publication.id])
    )[publication.id]
    return publication, target


@respx.mock
async def test_text_post_with_link(db_session):
    publication, target = await _target(
        db_session, "-text", content="Mirá https://tienda.example.com", media=[]
    )
    feed = respx.post(f"{_graph()}/{PAGE_ID}/feed").mock(
        return_value=httpx.Response(200, json={"id": f"{PAGE_ID}_1"})
    )
    respx.get(f"{_graph()}/{PAGE_ID}_1").mock(
        return_value=httpx.Response(
            200, json={"permalink_url": "https://www.facebook.com/p/1"}
        )
    )

    result = await FacebookPageAdapter().publish(db_session, publication, target)

    assert result.ok
    assert result.external_id == f"{PAGE_ID}_1"
    assert result.permalink == "https://www.facebook.com/p/1"
    sent = _form(feed.calls.last.request)
    assert sent["message"] == "Mirá https://tienda.example.com"
    assert sent["link"] == "https://tienda.example.com"
    # Token in the form body, not in the (logged) URL.
    assert sent["access_token"] == "PAGE-TOKEN"
    assert "access_token" not in feed.calls.last.request.url.params


@respx.mock
async def test_single_photo(db_session):
    publication, target = await _target(
        db_session, "-photo", content="Nueva", media=[IMG_A]
    )
    photos = respx.post(f"{_graph()}/{PAGE_ID}/photos").mock(
        return_value=httpx.Response(200, json={"id": "PH1", "post_id": f"{PAGE_ID}_2"})
    )
    respx.get(f"{_graph()}/{PAGE_ID}_2").mock(
        return_value=httpx.Response(200, json={"permalink_url": "https://fb/2"})
    )

    result = await FacebookPageAdapter().publish(db_session, publication, target)

    assert result.ok
    assert result.external_id == f"{PAGE_ID}_2"
    sent = _form(photos.calls.last.request)
    assert sent == {"url": IMG_A["url"], "message": "Nueva", "access_token": "PAGE-TOKEN"}


@respx.mock
async def test_several_photos_become_one_post(db_session):
    publication, target = await _target(
        db_session, "-album", content="Galería", media=[IMG_A, IMG_B]
    )
    photo_ids = iter(["PH1", "PH2"])
    photos = respx.post(f"{_graph()}/{PAGE_ID}/photos").mock(
        side_effect=lambda request: httpx.Response(200, json={"id": next(photo_ids)})
    )
    feed = respx.post(f"{_graph()}/{PAGE_ID}/feed").mock(
        return_value=httpx.Response(200, json={"id": f"{PAGE_ID}_3"})
    )
    respx.get(f"{_graph()}/{PAGE_ID}_3").mock(
        return_value=httpx.Response(200, json={"permalink_url": "https://fb/3"})
    )

    result = await FacebookPageAdapter().publish(db_session, publication, target)

    assert result.ok
    assert [_form(c.request)["published"] for c in photos.calls] == ["false", "false"]
    sent = _form(feed.calls.last.request)
    assert json.loads(sent["attached_media[0]"]) == {"media_fbid": "PH1"}
    assert json.loads(sent["attached_media[1]"]) == {"media_fbid": "PH2"}
    assert sent["message"] == "Galería"


@respx.mock
async def test_video_uses_the_video_host(db_session):
    publication, target = await _target(
        db_session, "-video", content="Clip", media=[VIDEO]
    )
    videos = respx.post(f"{_graph_video()}/{PAGE_ID}/videos").mock(
        return_value=httpx.Response(200, json={"id": "VID1"})
    )
    respx.get(f"{_graph()}/VID1").mock(
        return_value=httpx.Response(
            200, json={"permalink_url": f"/{PAGE_ID}/videos/VID1/"}
        )
    )

    result = await FacebookPageAdapter().publish(db_session, publication, target)

    assert result.ok
    assert result.permalink == f"https://www.facebook.com/{PAGE_ID}/videos/VID1/"
    sent = _form(videos.calls.last.request)
    assert sent == {"file_url": VIDEO["url"], "description": "Clip", "access_token": "PAGE-TOKEN"}


@pytest.mark.parametrize(
    ("code", "retryable", "fragment"),
    [
        (200, False, "pages_manage_posts"),
        (190, False, "Volvé a conectarla"),
        (4, True, "se reintenta"),
        (100, False, "Invalid parameter"),
    ],
)
@respx.mock
async def test_graph_errors_are_reported_in_spanish(
    db_session, code, retryable, fragment
):
    publication, target = await _target(
        db_session, f"-err{code}", content="x", media=[]
    )
    respx.post(f"{_graph()}/{PAGE_ID}/feed").mock(
        return_value=httpx.Response(
            400, json={"error": {"code": code, "message": "Invalid parameter"}}
        )
    )

    result = await FacebookPageAdapter().publish(db_session, publication, target)

    assert not result.ok
    assert result.retryable is retryable
    assert result.error_code == str(code)
    assert fragment in result.error_message


@respx.mock
async def test_network_failure_is_retryable(db_session):
    publication, target = await _target(db_session, "-net", content="x", media=[])
    respx.post(f"{_graph()}/{PAGE_ID}/feed").mock(
        side_effect=httpx.ConnectError("down")
    )

    result = await FacebookPageAdapter().publish(db_session, publication, target)

    assert not result.ok
    assert result.retryable


@respx.mock
async def test_timeout_is_not_retried(db_session):
    """It may have gone out: a retry could publish twice."""
    publication, target = await _target(db_session, "-tmo", content="x", media=[])
    respx.post(f"{_graph()}/{PAGE_ID}/feed").mock(
        side_effect=httpx.ReadTimeout("slow")
    )

    result = await FacebookPageAdapter().publish(db_session, publication, target)

    assert not result.ok
    assert not result.retryable
    assert "Revisá la página" in result.error_message


@respx.mock
async def test_permalink_failure_keeps_the_post_published(db_session):
    publication, target = await _target(db_session, "-perm", content="x", media=[])
    respx.post(f"{_graph()}/{PAGE_ID}/feed").mock(
        return_value=httpx.Response(200, json={"id": f"{PAGE_ID}_9"})
    )
    respx.get(f"{_graph()}/{PAGE_ID}_9").mock(side_effect=httpx.ConnectError("down"))

    result = await FacebookPageAdapter().publish(db_session, publication, target)

    assert result.ok
    assert result.external_id == f"{PAGE_ID}_9"
    assert result.permalink is None


async def test_validate_rejects_mixed_video_and_empty_posts(db_session):
    publication, target = await _target(db_session, "-val", content="x", media=[])
    adapter = FacebookPageAdapter()

    publication.media = [VIDEO, IMG_A]
    assert any("video se publica solo" in e for e in adapter.validate(publication, target))

    publication.media = []
    publication.content = "  "
    assert any("texto o al menos" in e for e in adapter.validate(publication, target))
