"""A small model running next to AloStudio (llama.cpp's ``llama-server``).

llama-server speaks OpenAI's chat completions, plus two things we rely on:

  * ``response_format`` with a JSON schema becomes a grammar, so the answer
    always has the shape we ask for (and an enum only allows its values);
  * ``cache_prompt`` keeps the processed prompt: the next request that
    starts the same way only processes what is new. On a 4-core VPS a 4B
    model reads 10 to 15 tokens a second, so a long fixed beginning (rules,
    examples, the help) is read once and each question costs only its own
    words.

Off unless ``local_llm_url`` is set (Ajustes → Instalación). Free: nothing
is recorded in the account's spend.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

# A request waits while another one is answered, and the first one after a
# restart reads the whole fixed beginning.
_TIMEOUT = httpx.Timeout(240.0, connect=5.0)

# llama-server keeps each slot's processed prompt. The help assistant's long
# fixed beginning lives in its own slot, so classifying conversations (F10,
# the other slot) never makes it read the help again (``ops/llm/levantar.sh``
# starts two slots).
HELP_SLOT = 0
DECISIONS_SLOT = 1


class LocalLlmError(RuntimeError):
    """``code``: ``unreachable`` | ``timeout`` | ``bad_response``."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def configured() -> bool:
    return bool(get_settings().local_llm_url)


# ``GET /props`` → ``total_slots``, kept a few minutes (it changes only when
# the server is started again).
_SLOTS_TTL_SECONDS = 300.0
_slots_seen: tuple[float, int] | None = None


async def slot_count() -> int:
    """How many slots llama-server runs; 1 when it can't tell."""
    global _slots_seen
    now = time.monotonic()
    if _slots_seen is not None and now - _slots_seen[0] < _SLOTS_TTL_SECONDS:
        return _slots_seen[1]
    url = f"{get_settings().local_llm_url.rstrip('/')}/props"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(url)
        count = int(resp.json().get("total_slots") or 1)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return 1
    _slots_seen = (now, count)
    return count


async def chat(
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float = 0.1,
    json_schema: dict[str, Any] | None = None,
    slot: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """The answer's text and llama-server's ``timings`` (tokens read from the
    cache, read anew and written, with their speeds)."""
    settings = get_settings()
    payload: dict[str, Any] = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "cache_prompt": True,
        # Qwen3's hybrid models think aloud unless told not to; the others
        # ignore it.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if settings.local_llm_model:
        payload["model"] = settings.local_llm_model
    if slot is not None:
        payload["id_slot"] = slot
    if json_schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "answer", "schema": json_schema},
        }
    url = f"{settings.local_llm_url.rstrip('/')}/v1/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
    except httpx.TimeoutException as exc:
        raise LocalLlmError("timeout") from exc
    except httpx.HTTPError as exc:
        raise LocalLlmError("unreachable", type(exc).__name__) from exc
    if resp.status_code >= 400:
        raise LocalLlmError("bad_response", f"HTTP {resp.status_code} {resp.text[:200]}")
    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LocalLlmError("bad_response", "no message") from exc
    if not isinstance(content, str):
        raise LocalLlmError("bad_response", "no text")
    timings = data.get("timings") if isinstance(data.get("timings"), dict) else {}
    return content, timings


def parse_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise LocalLlmError("bad_response", "not json") from exc
    if not isinstance(value, dict):
        raise LocalLlmError("bad_response", "not an object")
    return value


__all__ = [
    "DECISIONS_SLOT",
    "HELP_SLOT",
    "LocalLlmError",
    "chat",
    "configured",
    "parse_json",
    "slot_count",
]
