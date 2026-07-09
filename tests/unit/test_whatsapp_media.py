"""Unit tests for WhatsApp inbound media/location (no DB).

``download_and_store_media`` does the 2-step Graph fetch + a MinIO PUT (all
mocked via respx). ``_build_media_attachments`` turns a message payload into
attachment specs.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import respx

from app.core.config import get_settings
from app.domains.whatsapp import incoming_cloud
from app.domains.whatsapp.incoming_cloud import _build_media_attachments
from app.domains.whatsapp.media import download_and_store_media

_META = "https://graph.facebook.com/v13.0"


def _channel():
    return SimpleNamespace(
        account_id=2,
        provider_config={"api_key": "tok", "phone_number_id": "pid"},
    )


@respx.mock
async def test_download_and_store_media_roundtrip():
    respx.get(f"{_META}/MEDIA123").mock(
        return_value=httpx.Response(
            200, json={"url": "https://lookaside.fbsbx.com/m/1", "mime_type": "image/png"}
        )
    )
    respx.get("https://lookaside.fbsbx.com/m/1").mock(
        return_value=httpx.Response(200, content=b"\x89PNG bytes")
    )
    endpoint = get_settings().s3_endpoint_url.rstrip("/")
    put_route = respx.put(url__startswith=endpoint).mock(
        return_value=httpx.Response(200)
    )

    out = await download_and_store_media(
        _channel(), account_id=2, media_id="MEDIA123"
    )
    assert out is not None
    assert out["extension"] == "png"
    assert out["external_url"].endswith("accounts/2/whatsapp/MEDIA123.png")
    # the PUT carried the raw bytes + the media content-type
    assert put_route.called
    put_req = put_route.calls.last.request
    assert put_req.content == b"\x89PNG bytes"
    assert put_req.headers["content-type"] == "image/png"


@respx.mock
async def test_download_returns_none_on_graph_error():
    respx.get(f"{_META}/BAD").mock(return_value=httpx.Response(404))
    out = await download_and_store_media(
        _channel(), account_id=2, media_id="BAD"
    )
    assert out is None


async def test_build_location_attachment():
    msg = {
        "location": {
            "latitude": -34.9,
            "longitude": -56.16,
            "name": "Plaza Independencia",
            "address": "Montevideo",
            "url": "https://maps.example/x",
        }
    }
    atts, caption = await _build_media_attachments(
        channel=_channel(), msg=msg, msg_type="location"
    )
    assert caption is None
    assert len(atts) == 1
    a = atts[0]
    assert a.file_type == "location"
    assert a.coordinates_lat == -34.9
    assert a.coordinates_long == -56.16
    assert a.fallback_title == "Plaza Independencia, Montevideo"
    assert a.external_url == "https://maps.example/x"


async def test_build_media_attachment_uses_caption_as_content(monkeypatch):
    async def _fake_store(channel, *, account_id, media_id):
        return {"external_url": "http://minio/x.jpg", "extension": "jpg"}

    monkeypatch.setattr(
        incoming_cloud, "download_and_store_media", _fake_store
    )
    msg = {"image": {"id": "M1", "caption": "mirá esto", "mime_type": "image/jpeg"}}
    atts, caption = await _build_media_attachments(
        channel=_channel(), msg=msg, msg_type="image"
    )
    assert caption == "mirá esto"
    assert len(atts) == 1 and atts[0].file_type == "image"
    assert atts[0].external_url == "http://minio/x.jpg"


async def test_failed_media_download_keeps_caption_no_attachment(monkeypatch):
    async def _fail(channel, *, account_id, media_id):
        return None

    monkeypatch.setattr(incoming_cloud, "download_and_store_media", _fail)
    msg = {"document": {"id": "D1", "caption": "el pdf"}}
    atts, caption = await _build_media_attachments(
        channel=_channel(), msg=msg, msg_type="document"
    )
    assert atts == []
    assert caption == "el pdf"
