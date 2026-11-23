"""The "Free" model: a small model next to AloStudio (llama.cpp's
``llama-server``) or a free hosted one (Groq, NVIDIA NIM), with an optional
second provider that answers when the first one cannot.

Every provider speaks OpenAI's chat completions at ``{url}/v1/chat/completions``
(Groq: ``https://api.groq.com/openai``; NVIDIA: ``https://integrate.api.nvidia.com``).

A local llama-server (no key) gets two extras we rely on:

  * ``response_format`` with a JSON schema becomes a grammar, so the answer
    always has the shape we ask for (and an enum only allows its values);
  * ``cache_prompt`` keeps the processed prompt in a slot: the next request
    that starts the same way only processes what is new. On a 4-core VPS a
    4B model reads 10 to 15 tokens a second, so a long fixed beginning is
    read once.

A hosted provider (it has a key) gets plain OpenAI: ``json_object`` instead
of a grammar (the callers check the shape anyway), no slots, no cache. When
it refuses (rate limit, error, timeout) the second provider, if any, is
asked the same.

Off unless ``local_llm_url`` is set (Ajustes → Instalación). Free: nothing
is recorded in the account's spend.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

# A request waits while another one is answered, and the first one after a
# restart reads the whole fixed beginning.
_TIMEOUT = httpx.Timeout(240.0, connect=5.0)
# A hosted provider answers in seconds; past this, try the other one.
_REMOTE_TIMEOUT = httpx.Timeout(45.0, connect=5.0)

# llama-server keeps each slot's processed prompt. The help assistant's long
# fixed beginning lives in its own slot, so classifying conversations (F10,
# the other slot) never makes it read the help again (``ops/llm/levantar.sh``
# starts two slots).
HELP_SLOT = 0
DECISIONS_SLOT = 1


class LocalLlmError(RuntimeError):
    """``code``: ``unreachable`` | ``timeout`` | ``rate_limited`` |
    ``bad_response``."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Provider:
    url: str
    key: str
    model: str

    @property
    def hosted(self) -> bool:
        """A hosted API (Groq, NVIDIA…) rather than our own llama-server."""
        return bool(self.key)


def providers() -> list[Provider]:
    """The main provider, then the backup, as configured."""
    s = get_settings()
    found = []
    if s.local_llm_url:
        found.append(Provider(s.local_llm_url, s.local_llm_api_key, s.local_llm_model))
    if s.local_llm_url and s.local_llm_fallback_url:
        found.append(
            Provider(
                s.local_llm_fallback_url, s.local_llm_fallback_api_key, s.local_llm_fallback_model
            )
        )
    return found


def configured() -> bool:
    return bool(get_settings().local_llm_url)


def hosted() -> bool:
    """The main provider is a hosted API: no slots to share, nothing to warm."""
    found = providers()
    return bool(found) and found[0].hosted


# ``GET /props`` → ``total_slots``, kept a few minutes (it changes only when
# the server is started again).
_SLOTS_TTL_SECONDS = 300.0
_slots_seen: tuple[float, int] | None = None


async def slot_count() -> int:
    """How many slots llama-server runs; 1 when it can't tell. A hosted
    provider has no slots to share, so it counts as plenty."""
    global _slots_seen
    if hosted():
        return 2
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
    """The answer's text and, from llama-server, its ``timings`` (tokens read
    from the cache, read anew and written). Tries the backup provider when
    the main one fails."""
    found = providers()
    if not found:
        raise LocalLlmError("unreachable", "not configured")
    last: LocalLlmError | None = None
    for index, provider in enumerate(found):
        try:
            return await _ask(provider, messages, max_tokens, temperature, json_schema, slot)
        except LocalLlmError as exc:
            last = exc
            if index + 1 < len(found):
                log.warning("local_llm.fallback from=%s code=%s", _host(provider), exc.code)
    assert last is not None
    raise last


async def _ask(
    provider: Provider,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    json_schema: dict[str, Any] | None,
    slot: int | None,
) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if provider.model:
        payload["model"] = provider.model
    headers = {"Content-Type": "application/json"}
    if provider.hosted:
        headers["Authorization"] = f"Bearer {provider.key}"
        if json_schema is not None:
            payload["messages"] = _say_json(messages)
            payload["response_format"] = {"type": "json_object"}
    else:
        payload["cache_prompt"] = True
        # Qwen3's hybrid models think aloud unless told not to; the others
        # ignore it.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        if slot is not None:
            payload["id_slot"] = slot
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "answer", "schema": json_schema},
            }
    url = f"{provider.url.rstrip('/')}/v1/chat/completions"
    try:
        async with httpx.AsyncClient(
            timeout=_REMOTE_TIMEOUT if provider.hosted else _TIMEOUT
        ) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise LocalLlmError("timeout") from exc
    except httpx.HTTPError as exc:
        raise LocalLlmError("unreachable", type(exc).__name__) from exc
    if resp.status_code == 429:
        raise LocalLlmError("rate_limited", _host(provider))
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


def _say_json(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """OpenAI-style JSON mode wants the word "JSON" in the request."""
    if any("json" in str(m.get("content", "")).lower() for m in messages):
        return messages
    return [{"role": "system", "content": "Respond only with a JSON object."}, *messages]


def _host(provider: Provider) -> str:
    return re.sub(r"^https?://", "", provider.url).split("/")[0]


_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def parse_json(text: str) -> dict[str, Any]:
    """The object in ``text``; hosted models sometimes wrap it in a
    Markdown code block."""
    stripped = text.strip()
    match = _FENCE.match(stripped)
    if match:
        stripped = match.group(1)
    try:
        value = json.loads(stripped)
    except ValueError as exc:
        raise LocalLlmError("bad_response", "not json") from exc
    if not isinstance(value, dict):
        raise LocalLlmError("bad_response", "not an object")
    return value


__all__ = [
    "DECISIONS_SLOT",
    "HELP_SLOT",
    "LocalLlmError",
    "Provider",
    "chat",
    "configured",
    "hosted",
    "parse_json",
    "providers",
    "slot_count",
]
