"""Images and audio to text with the free hosted models: NVIDIA first, Groq
when NVIDIA cannot (out of credits, rate limit, error).

  * an image (a screenshot) becomes a short description;
  * an audio (a voice question) becomes its transcription.

The text then goes to whichever model answers (the help's Free or Fast), so
neither needs to read images or audio itself.

Measured with CTC's keys (2026-11-20): NVIDIA's ``nemotron-3-nano-omni``
reads both in 1 to 3 seconds; on Groq, ``whisper-large-v3-turbo`` transcribes
in 0.1 s and ``qwen3.8-27b`` reads images in 0.5 s. The keys are the Free
model's ones (``LOCAL_LLM_*``): whichever of the two providers points to
nvidia.com or groq.com. When neither answers, :class:`MediaAiDown`.
"""

from __future__ import annotations

import base64
import logging

import httpx

from app.core import local_llm

log = logging.getLogger(__name__)

NVIDIA_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
GROQ_IMAGE_MODEL = "qwen/qwen3.8-27b"
GROQ_AUDIO_MODEL = "whisper-large-v3-turbo"

IMAGE_MAX_BYTES = 5 * 1024 * 1024
AUDIO_MAX_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = ("image/png", "image/jpeg", "image/webp")
AUDIO_TYPES = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp4": "mp4",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}
# Words the speech models get wrong without a hint ("Halo Studio").
VOCABULARY = "AloStudio"

_TIMEOUT = httpx.Timeout(60.0, connect=5.0)

_DESCRIBE = (
    "Describí en español, en 1 a 3 oraciones, lo que muestra esta captura de "
    "pantalla: qué pantalla de AloStudio es, qué se ve seleccionado o abierto y "
    "cualquier mensaje de error que aparezca. Solo lo que se ve."
)
_TRANSCRIBE = (
    f"Transcribí exactamente lo que dice este audio, en español. El programa se llama "
    f"{VOCABULARY}. Respondé solo con la transcripción."
)


class MediaAiDown(RuntimeError):
    """Neither NVIDIA nor Groq could read it."""


class MediaRejected(ValueError):
    """``code``: ``type`` or ``size``."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _keys() -> tuple[str | None, str | None]:
    nvidia = groq = None
    for provider in local_llm.providers():
        if not provider.hosted:
            continue
        if "nvidia.com" in provider.url:
            nvidia = provider.key
        elif "groq.com" in provider.url:
            groq = provider.key
    return nvidia, groq


def available() -> bool:
    return any(_keys())


def check(kind: str, mime: str, data: bytes) -> None:
    """Raises :class:`MediaRejected` for a type or size we do not take."""
    if kind == "image":
        if mime not in IMAGE_TYPES:
            raise MediaRejected("type")
        if len(data) > IMAGE_MAX_BYTES:
            raise MediaRejected("size")
    else:
        if mime.split(";")[0] not in AUDIO_TYPES:
            raise MediaRejected("type")
        if len(data) > AUDIO_MAX_BYTES:
            raise MediaRejected("size")


async def describe(data: bytes, mime: str) -> str:
    nvidia, groq = _keys()
    url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    content = [
        {"type": "text", "text": _DESCRIBE},
        {"type": "image_url", "image_url": {"url": url}},
    ]
    attempts = []
    if nvidia:
        attempts.append(("nvidia", nvidia, NVIDIA_MODEL))
    if groq:
        attempts.append(("groq", groq, GROQ_IMAGE_MODEL))
    for name, key, model in attempts:
        try:
            return await _chat(name, key, model, content)
        except _Failed as exc:
            log.warning("media_ai.describe_failed provider=%s reason=%s", name, exc)
    raise MediaAiDown("image")


async def transcribe(data: bytes, mime: str) -> str:
    nvidia, groq = _keys()
    fmt = AUDIO_TYPES.get(mime.split(";")[0], "webm")
    if nvidia:
        content = [
            {"type": "text", "text": _TRANSCRIBE},
            {
                "type": "input_audio",
                "input_audio": {"data": base64.b64encode(data).decode(), "format": fmt},
            },
        ]
        try:
            return await _chat("nvidia", nvidia, NVIDIA_MODEL, content)
        except _Failed as exc:
            log.warning("media_ai.transcribe_failed provider=nvidia reason=%s", exc)
    if groq:
        try:
            return await _whisper(groq, data, mime, fmt)
        except _Failed as exc:
            log.warning("media_ai.transcribe_failed provider=groq reason=%s", exc)
    raise MediaAiDown("audio")


class _Failed(Exception):
    pass


_BASES = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "groq": "https://api.groq.com/openai/v1",
}


async def _chat(name: str, key: str, model: str, content: list) -> str:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_BASES[name]}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                # Room for the reasoning models to think before answering.
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": 900,
                    "temperature": 0.1,
                },
            )
    except httpx.HTTPError as exc:
        raise _Failed(type(exc).__name__) from exc
    if resp.status_code >= 400:
        raise _Failed(f"HTTP {resp.status_code}")
    try:
        text = resp.json()["choices"][0]["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise _Failed("no message") from exc
    text = text.strip()
    if not text:
        raise _Failed("empty")
    return text[:1000]


async def _whisper(key: str, data: bytes, mime: str, fmt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_BASES['groq']}/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": (f"audio.{fmt}", data, mime.split(";")[0])},
                data={"model": GROQ_AUDIO_MODEL, "language": "es", "prompt": VOCABULARY},
            )
    except httpx.HTTPError as exc:
        raise _Failed(type(exc).__name__) from exc
    if resp.status_code >= 400:
        raise _Failed(f"HTTP {resp.status_code}")
    try:
        text = str(resp.json().get("text") or "").strip()
    except ValueError as exc:
        raise _Failed("no text") from exc
    if not text:
        raise _Failed("empty")
    return text[:1000]


__all__ = [
    "AUDIO_MAX_BYTES",
    "IMAGE_MAX_BYTES",
    "MediaAiDown",
    "MediaRejected",
    "available",
    "check",
    "describe",
    "transcribe",
]
