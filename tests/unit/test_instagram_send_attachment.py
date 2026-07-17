"""Unit tests for the Instagram outbound attachment path (no DB).

Covers Rails' ``attachment_type`` degradation plus the upload hop we do in
place of its public-URL pull: Meta gives us a reusable ``attachment_id`` for
the bytes, which avoids handing it a URL that races our own commit.

Anchors:
  reference/chatwoot/app/services/instagram/base_send_service.rb
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import respx

from app.core.config import get_settings
from app.domains.instagram.sender import (
    _send_attachment_type,
    _upload_attachment,
)

_BLOB_URL = "http://minio.test/x.jpg"


def _channel():
    return SimpleNamespace(id=1, access_token="PAGE_TOK")


def _attachment(**overrides):
    base = {
        "id": 9,
        "extension": "jpg",
        "external_url": _BLOB_URL,
        "file_type_str": "image",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _uploads_route():
    version = get_settings().facebook_api_version
    return f"https://graph.facebook.com/{version}/me/message_attachments"


# ---------------------------------------------------------------------------
# attachment_type (Rails' allow-list)
# ---------------------------------------------------------------------------
def test_send_attachment_type_passes_meta_known_types():
    for known in ("image", "audio", "video", "file"):
        assert _send_attachment_type(known) == known


def test_send_attachment_type_degrades_unknown_to_file():
    """Meta's Send API has no ig_post/share/story_mention — Rails sends
    those as a plain ``file``."""
    for ours in ("ig_post", "ig_story", "ig_reel", "share", "story_mention"):
        assert _send_attachment_type(ours) == "file"


# ---------------------------------------------------------------------------
# _upload_attachment
# ---------------------------------------------------------------------------
@respx.mock
async def test_upload_attachment_returns_reusable_id():
    respx.get(_BLOB_URL).mock(
        return_value=httpx.Response(200, content=b"JPEGBYTES")
    )
    route = respx.post(_uploads_route()).mock(
        return_value=httpx.Response(200, json={"attachment_id": "AID-1"})
    )

    out = await _upload_attachment(_channel(), _attachment())
    assert out == "AID-1"
    # the multipart body carries the blob itself + the reusable envelope
    body = route.calls.last.request.content
    assert b"JPEGBYTES" in body
    assert b"is_reusable" in body


@respx.mock
async def test_upload_sends_degraded_type_for_ig_specific_media():
    respx.get(_BLOB_URL).mock(return_value=httpx.Response(200, content=b"x"))
    route = respx.post(_uploads_route()).mock(
        return_value=httpx.Response(200, json={"attachment_id": "AID-2"})
    )
    await _upload_attachment(_channel(), _attachment(file_type_str="ig_post"))
    assert b'"type": "file"' in route.calls.last.request.content


@respx.mock
async def test_upload_returns_none_on_meta_error():
    respx.get(_BLOB_URL).mock(return_value=httpx.Response(200, content=b"x"))
    respx.post(_uploads_route()).mock(
        return_value=httpx.Response(400, json={"error": {"message": "nope"}})
    )
    assert await _upload_attachment(_channel(), _attachment()) is None


@respx.mock
async def test_upload_returns_none_when_blob_is_gone():
    respx.get(_BLOB_URL).mock(return_value=httpx.Response(404))
    assert await _upload_attachment(_channel(), _attachment()) is None


@respx.mock
async def test_upload_returns_none_when_meta_omits_the_id():
    respx.get(_BLOB_URL).mock(return_value=httpx.Response(200, content=b"x"))
    respx.post(_uploads_route()).mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    assert await _upload_attachment(_channel(), _attachment()) is None
