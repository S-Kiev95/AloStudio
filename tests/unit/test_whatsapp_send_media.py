"""Unit tests for outbound WhatsApp media send (no DB).

``send_media_message_cloud`` does 3 hops — fetch bytes from the store, upload
to Meta's ``/media``, then send a ``type=<media>`` message — all mocked via
respx. A tiny fake session stands in for the WAMID stamp.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import respx

import app.main  # noqa: F401  (register SQLModel mappers)
from app.domains.conversations.models import Attachment, Message
from app.domains.whatsapp.cloud_provider import send_media_message_cloud

_PID = "https://graph.facebook.com/v13.0/PID"


class _FakeSession:
    def add(self, *_a: object) -> None:
        pass

    async def flush(self) -> None:
        pass


def _channel() -> SimpleNamespace:
    return SimpleNamespace(
        id=1, provider_config={"api_key": "tok", "phone_number_id": "PID"}
    )


@respx.mock
async def test_image_uploads_then_sends_with_caption():
    att = Attachment(
        external_url="http://ext.test/x.png",
        file_type=0,  # image
        extension="png",
        account_id=1,
        message_id=5,
    )
    msg = Message(id=5, content="mirá", account_id=1)
    respx.get("http://ext.test/x.png").mock(
        return_value=httpx.Response(
            200, content=b"PNG", headers={"content-type": "image/png"}
        )
    )
    up = respx.post(f"{_PID}/media").mock(
        return_value=httpx.Response(200, json={"id": "MEDIA1"})
    )
    send = respx.post(f"{_PID}/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.X"}]})
    )

    ok = await send_media_message_cloud(
        _FakeSession(), channel=_channel(), message=msg, to_phone="59899",
        attachment=att,
    )
    assert ok is True
    assert msg.source_id == "wamid.X"
    assert up.called  # media uploaded first
    body = json.loads(send.calls.last.request.content)
    assert body["type"] == "image"
    assert body["image"] == {"id": "MEDIA1", "caption": "mirá"}


@respx.mock
async def test_audio_has_no_caption():
    att = Attachment(
        external_url="http://ext.test/a.oga", file_type=1, extension="oga",
        account_id=1, message_id=6,
    )
    msg = Message(id=6, content="nota", account_id=1)
    respx.get("http://ext.test/a.oga").mock(
        return_value=httpx.Response(
            200, content=b"OGA", headers={"content-type": "audio/ogg"}
        )
    )
    respx.post(f"{_PID}/media").mock(
        return_value=httpx.Response(200, json={"id": "M2"})
    )
    send = respx.post(f"{_PID}/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "w2"}]})
    )
    ok = await send_media_message_cloud(
        _FakeSession(), channel=_channel(), message=msg, to_phone="1",
        attachment=att,
    )
    assert ok is True
    body = json.loads(send.calls.last.request.content)
    assert body["type"] == "audio"
    assert "caption" not in body["audio"]


@respx.mock
async def test_document_carries_filename():
    att = Attachment(
        external_url="http://ext.test/d.pdf", file_type=3, extension="pdf",
        account_id=1, message_id=7,
    )
    msg = Message(id=7, content=None, account_id=1)
    respx.get("http://ext.test/d.pdf").mock(
        return_value=httpx.Response(
            200, content=b"PDF", headers={"content-type": "application/pdf"}
        )
    )
    respx.post(f"{_PID}/media").mock(
        return_value=httpx.Response(200, json={"id": "M3"})
    )
    send = respx.post(f"{_PID}/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "w3"}]})
    )
    ok = await send_media_message_cloud(
        _FakeSession(), channel=_channel(), message=msg, to_phone="1",
        attachment=att,
    )
    assert ok is True
    body = json.loads(send.calls.last.request.content)
    assert body["type"] == "document"
    assert body["document"]["id"] == "M3"
    assert body["document"]["filename"].endswith(".pdf")


@respx.mock
async def test_upload_error_returns_false():
    att = Attachment(
        external_url="http://ext.test/x.png", file_type=0, extension="png",
        account_id=1, message_id=8,
    )
    msg = Message(id=8, content="x", account_id=1)
    respx.get("http://ext.test/x.png").mock(
        return_value=httpx.Response(200, content=b"PNG")
    )
    respx.post(f"{_PID}/media").mock(return_value=httpx.Response(401))
    ok = await send_media_message_cloud(
        _FakeSession(), channel=_channel(), message=msg, to_phone="1",
        attachment=att,
    )
    assert ok is False
    assert msg.source_id is None
