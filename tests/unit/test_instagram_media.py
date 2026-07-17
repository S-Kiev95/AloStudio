"""Unit tests for Instagram inbound media (no DB).

``download_and_store_ig_media`` does a single CDN GET + a MinIO PUT (both
mocked via respx) — Instagram signs the URL into the webhook, so there is no
``media_id`` round-trip like WhatsApp. ``_build_ig_attachments`` turns a
``message.attachments[]`` block into attachment specs.

Anchors:
  reference/chatwoot/app/builders/messages/messenger/message_builder.rb
    (``process_attachment`` / ``file_type_params`` / ``facebook_reel?``)
"""

from __future__ import annotations

from typing import Any

import httpx
import respx

from app.core.config import get_settings
from app.domains.instagram import incoming
from app.domains.instagram.incoming import (
    _all_ig_attachments_unsupported,
    _build_ig_attachments,
)
from app.domains.instagram.media import download_and_store_ig_media

_CDN = "https://lookaside.fbsbx.com/ig"


def _block(attachments: list[dict[str, Any]]) -> dict[str, Any]:
    return {"mid": "MID-1", "attachments": attachments}


async def _unused_fetch(*, account_id, url, key_hint):
    """Stand-in for the downloader on paths that must never fetch."""
    raise AssertionError("this attachment type has no file to download")


# ---------------------------------------------------------------------------
# download_and_store_ig_media
# ---------------------------------------------------------------------------
@respx.mock
async def test_download_and_store_ig_media_roundtrip():
    respx.get(f"{_CDN}/1").mock(
        return_value=httpx.Response(
            200, content=b"\x89PNG bytes", headers={"content-type": "image/png"}
        )
    )
    endpoint = get_settings().s3_endpoint_url.rstrip("/")
    put_route = respx.put(url__startswith=endpoint).mock(
        return_value=httpx.Response(200)
    )

    out = await download_and_store_ig_media(
        account_id=7, url=f"{_CDN}/1", key_hint="MID-1:0"
    )
    assert out is not None
    assert out["extension"] == "png"
    assert "accounts/7/instagram/" in out["external_url"]
    assert out["external_url"].endswith(".png")
    # the PUT carried the raw bytes + the CDN's content-type
    assert put_route.called
    put_req = put_route.calls.last.request
    assert put_req.content == b"\x89PNG bytes"
    assert put_req.headers["content-type"] == "image/png"


@respx.mock
async def test_same_key_hint_is_deterministic():
    """A duplicate re-delivery overwrites rather than piling up objects."""
    respx.get(f"{_CDN}/2").mock(
        return_value=httpx.Response(
            200, content=b"jpg", headers={"content-type": "image/jpeg"}
        )
    )
    respx.put(url__startswith=get_settings().s3_endpoint_url.rstrip("/")).mock(
        return_value=httpx.Response(200)
    )
    first = await download_and_store_ig_media(
        account_id=1, url=f"{_CDN}/2", key_hint="MID-X:0"
    )
    second = await download_and_store_ig_media(
        account_id=1, url=f"{_CDN}/2", key_hint="MID-X:0"
    )
    assert first is not None and second is not None
    assert first["external_url"] == second["external_url"]


@respx.mock
async def test_download_returns_none_on_cdn_error():
    respx.get(f"{_CDN}/bad").mock(return_value=httpx.Response(404))
    out = await download_and_store_ig_media(
        account_id=1, url=f"{_CDN}/bad", key_hint="k"
    )
    assert out is None


# ---------------------------------------------------------------------------
# _build_ig_attachments
# ---------------------------------------------------------------------------
async def test_build_image_attachment(monkeypatch):
    async def _fake(*, account_id, url, key_hint):
        return {"external_url": "http://minio/x.jpg", "extension": "jpg"}

    monkeypatch.setattr(incoming, "download_and_store_ig_media", _fake)
    specs, fallback = await _build_ig_attachments(
        account_id=1,
        message_block=_block(
            [{"type": "image", "payload": {"url": f"{_CDN}/x.jpg"}}]
        ),
        mid="MID-1",
    )
    assert fallback is None
    assert len(specs) == 1
    assert specs[0].file_type == "image"
    assert specs[0].external_url == "http://minio/x.jpg"
    assert specs[0].extension == "jpg"


async def test_multiple_attachments_all_land(monkeypatch):
    async def _fake(*, account_id, url, key_hint):
        return {"external_url": f"http://minio/{key_hint}", "extension": None}

    monkeypatch.setattr(incoming, "download_and_store_ig_media", _fake)
    specs, _ = await _build_ig_attachments(
        account_id=1,
        message_block=_block(
            [
                {"type": "image", "payload": {"url": f"{_CDN}/a"}},
                {"type": "video", "payload": {"url": f"{_CDN}/b"}},
            ]
        ),
        mid="MID-1",
    )
    assert [s.file_type for s in specs] == ["image", "video"]
    # key_hint disambiguates attachments within the one message
    assert specs[0].external_url != specs[1].external_url


async def test_reel_keeps_permalink_and_skips_download(monkeypatch):
    called = False

    async def _fake(*, account_id, url, key_hint):
        nonlocal called
        called = True
        return {"external_url": "downloaded", "extension": None}

    monkeypatch.setattr(incoming, "download_and_store_ig_media", _fake)
    specs, fallback = await _build_ig_attachments(
        account_id=1,
        message_block=_block(
            [{"type": "reel", "payload": {"url": "https://facebook.com/reel/9"}}]
        ),
        mid="MID-1",
    )
    # a reel URL is a webpage, not a video file — Rails skips the fetch
    assert called is False
    assert fallback == "https://facebook.com/reel/9"
    assert len(specs) == 1
    assert specs[0].file_type == "ig_reel"
    assert specs[0].external_url == "https://facebook.com/reel/9"


async def test_ig_story_uses_story_media_url(monkeypatch):
    seen: dict[str, str] = {}

    async def _fake(*, account_id, url, key_hint):
        seen["url"] = url
        return {"external_url": "http://minio/s.jpg", "extension": "jpg"}

    monkeypatch.setattr(incoming, "download_and_store_ig_media", _fake)
    specs, _ = await _build_ig_attachments(
        account_id=1,
        message_block=_block(
            [
                {
                    "type": "ig_story",
                    "payload": {
                        "story_media_url": f"{_CDN}/story.jpg",
                        "url": "https://ignore.me",
                    },
                }
            ]
        ),
        mid="MID-1",
    )
    assert seen["url"] == f"{_CDN}/story.jpg"
    assert specs[0].file_type == "ig_story"


async def test_unsupported_types_are_skipped(monkeypatch):
    async def _fake(*, account_id, url, key_hint):
        raise AssertionError("must not download an unsupported type")

    monkeypatch.setattr(incoming, "download_and_store_ig_media", _fake)
    specs, fallback = await _build_ig_attachments(
        account_id=1,
        message_block=_block(
            [{"type": "template", "payload": {"url": f"{_CDN}/t"}}]
        ),
        mid="MID-1",
    )
    assert specs == []
    assert fallback is None


async def test_failed_download_drops_only_that_attachment(monkeypatch):
    async def _fail(*, account_id, url, key_hint):
        return None

    monkeypatch.setattr(incoming, "download_and_store_ig_media", _fail)
    specs, _ = await _build_ig_attachments(
        account_id=1,
        message_block=_block(
            [{"type": "image", "payload": {"url": f"{_CDN}/x"}}]
        ),
        mid="MID-1",
    )
    assert specs == []


async def test_attachment_without_url_is_skipped(monkeypatch):
    async def _fake(*, account_id, url, key_hint):
        raise AssertionError("no url → no download")

    monkeypatch.setattr(incoming, "download_and_store_ig_media", _fake)
    specs, _ = await _build_ig_attachments(
        account_id=1,
        message_block=_block([{"type": "image", "payload": {}}]),
        mid="MID-1",
    )
    assert specs == []


async def test_location_attachment_uses_coordinates(monkeypatch):
    async def _fake(*, account_id, url, key_hint):
        raise AssertionError("a location has no file to download")

    monkeypatch.setattr(incoming, "download_and_store_ig_media", _fake)
    specs, _ = await _build_ig_attachments(
        account_id=1,
        message_block=_block(
            [
                {
                    "type": "location",
                    # Rails reads url/title off the attachment, not the payload
                    "title": "Plaza Independencia",
                    "url": "https://maps.example/x",
                    "payload": {"coordinates": {"lat": -34.9, "long": -56.16}},
                }
            ]
        ),
        mid="MID-1",
    )
    assert len(specs) == 1
    a = specs[0]
    assert a.file_type == "location"
    assert a.coordinates_lat == -34.9
    assert a.coordinates_long == -56.16
    assert a.fallback_title == "Plaza Independencia"
    assert a.external_url == "https://maps.example/x"


async def test_location_without_coordinates_is_skipped(monkeypatch):
    monkeypatch.setattr(incoming, "download_and_store_ig_media", _unused_fetch)
    specs, _ = await _build_ig_attachments(
        account_id=1,
        message_block=_block([{"type": "location", "payload": {}}]),
        mid="MID-1",
    )
    assert specs == []


async def test_fallback_attachment_keeps_link(monkeypatch):
    monkeypatch.setattr(incoming, "download_and_store_ig_media", _unused_fetch)
    specs, _ = await _build_ig_attachments(
        account_id=1,
        message_block=_block(
            [{"type": "fallback", "title": "Un link", "url": "https://ex.com/a"}]
        ),
        mid="MID-1",
    )
    assert len(specs) == 1
    assert specs[0].file_type == "fallback"
    assert specs[0].fallback_title == "Un link"
    assert specs[0].external_url == "https://ex.com/a"


async def test_unknown_type_is_logged_and_skipped(monkeypatch, caplog):
    """Meta keeps adding shapes — an unknown one must be visible, not a
    silently empty message."""
    monkeypatch.setattr(incoming, "download_and_store_ig_media", _unused_fetch)
    with caplog.at_level("INFO"):
        specs, _ = await _build_ig_attachments(
            account_id=1,
            message_block=_block(
                [{"type": "brand_new_meta_thing", "payload": {"url": "u"}}]
            ),
            mid="MID-9",
        )
    assert specs == []
    assert "unhandled_attachment" in caplog.text
    assert "brand_new_meta_thing" in caplog.text


# ---------------------------------------------------------------------------
# _all_ig_attachments_unsupported (Rails' all_unsupported_files?)
# ---------------------------------------------------------------------------
def test_all_unsupported_detection():
    assert _all_ig_attachments_unsupported(_block([{"type": "template"}])) is True
    assert (
        _all_ig_attachments_unsupported(
            _block([{"type": "template"}, {"type": "image"}])
        )
        is False
    )
    assert _all_ig_attachments_unsupported(_block([])) is False
    assert _all_ig_attachments_unsupported({}) is False
