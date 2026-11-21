"""Images and audio to text: NVIDIA first, Groq when it cannot, and "down"
when neither can."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest
import respx

from app.core import media_ai
from app.core.config import get_settings

NVIDIA = "https://integrate.api.nvidia.com/v1/chat/completions"
GROQ_CHAT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_AUDIO = "https://api.groq.com/openai/v1/audio/transcriptions"


def _said(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


@pytest.fixture
def keys(monkeypatch) -> Iterator[None]:
    s = get_settings()
    monkeypatch.setattr(s, "local_llm_url", "https://api.groq.com/openai")
    monkeypatch.setattr(s, "local_llm_api_key", "gsk-test")
    monkeypatch.setattr(s, "local_llm_model", "openai/gpt-oss-20b")
    monkeypatch.setattr(s, "local_llm_fallback_url", "https://integrate.api.nvidia.com")
    monkeypatch.setattr(s, "local_llm_fallback_api_key", "nvapi-test")
    monkeypatch.setattr(s, "local_llm_fallback_model", "minimaxai/minimax-m3.1-flash")
    yield


async def test_an_image_goes_to_nvidia_first(keys):
    with respx.mock() as mock:
        nvidia = mock.post(NVIDIA).mock(return_value=_said("La pantalla de Ajustes de AloStudio."))
        text = await media_ai.describe(b"\x89PNG", "image/png")
    assert text == "La pantalla de Ajustes de AloStudio."
    sent = json.loads(nvidia.calls[0].request.content)
    assert sent["model"] == media_ai.NVIDIA_MODEL
    image = sent["messages"][0]["content"][1]["image_url"]["url"]
    assert image.startswith("data:image/png;base64,")


async def test_without_nvidia_credits_groq_reads_it(keys):
    with respx.mock() as mock:
        mock.post(NVIDIA).mock(return_value=httpx.Response(429))
        groq = mock.post(GROQ_CHAT).mock(return_value=_said("Ajustes de AloStudio."))
        text = await media_ai.describe(b"\x89PNG", "image/png")
    assert text == "Ajustes de AloStudio."
    assert json.loads(groq.calls[0].request.content)["model"] == media_ai.GROQ_IMAGE_MODEL


async def test_an_empty_answer_counts_as_a_failure(keys):
    with respx.mock() as mock:
        mock.post(NVIDIA).mock(return_value=_said(""))
        whisper = mock.post(GROQ_AUDIO).mock(
            return_value=httpx.Response(200, json={"text": " ¿Cómo cambio mi contraseña?"})
        )
        text = await media_ai.transcribe(b"OggS", "audio/ogg;codecs=opus")
    assert text == "¿Cómo cambio mi contraseña?"
    body = whisper.calls[0].request.content
    assert b"whisper-large-v3-turbo" in body and b"AloStudio" in body


async def test_when_neither_can_it_is_down(keys):
    with respx.mock() as mock:
        mock.post(NVIDIA).mock(return_value=httpx.Response(503))
        mock.post(GROQ_AUDIO).mock(return_value=httpx.Response(429))
        mock.post(GROQ_CHAT).mock(side_effect=httpx.ReadTimeout("x"))
        with pytest.raises(media_ai.MediaAiDown):
            await media_ai.transcribe(b"OggS", "audio/webm")
        with pytest.raises(media_ai.MediaAiDown):
            await media_ai.describe(b"\x89PNG", "image/jpeg")


def test_only_groq_or_nvidia_keys_count(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "local_llm_url", "http://127.0.0.1:8092")
    monkeypatch.setattr(s, "local_llm_api_key", "")
    monkeypatch.setattr(s, "local_llm_fallback_url", "")
    assert media_ai.available() is False


@pytest.mark.parametrize(
    ("kind", "mime", "size", "code"),
    [
        ("image", "image/gif", 10, "type"),
        ("image", "image/png", media_ai.IMAGE_MAX_BYTES + 1, "size"),
        ("audio", "video/mp4", 10, "type"),
        ("audio", "audio/webm", media_ai.AUDIO_MAX_BYTES + 1, "size"),
    ],
)
def test_what_is_not_taken(kind, mime, size, code):
    with pytest.raises(media_ai.MediaRejected) as caught:
        media_ai.check(kind, mime, b"x" * size)
    assert caught.value.code == code
