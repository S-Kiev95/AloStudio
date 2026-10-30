"""Minimal async OpenAI client for Help-Center embedding search and the
agent chat.

Ports the pieces of Chatwoot's Captain LLM stack that the Help-Center
semantic search actually uses:

  * ``Captain::Llm::EmbeddingService#get_embedding`` → :func:`embed_text`
  * ``Enterprise::Concerns::Article#generate_article_search_terms`` →
    :func:`generate_search_terms` (a ``gpt-4o`` JSON-mode completion that
    expands an article into diverse search terms)

and adds :func:`chat_completion`, one step of the agent chat
(``app.domains.agent``) with function calling.

We talk to the REST API over ``httpx`` directly rather than pulling in the
``openai`` SDK — two endpoints, no streaming. Everything is gated on
``settings.openai_api_key``: with no key the feature is off and callers
fall back to ILIKE search.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

# Must match the ``vector(1536)`` column on ``article_embeddings``. We pass
# it as ``dimensions`` so a 3-large model still projects down to fit.
EMBEDDING_DIM = 1536

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# A chat step can think before calling a tool or answering.
_CHAT_TIMEOUT = httpx.Timeout(90.0, connect=10.0)
# Room for the model's reasoning plus a short answer.
_CHAT_MAX_COMPLETION_TOKENS = 4096

_SEARCH_TERMS_SYSTEM_PROMPT = (
    "For the provided article content, generate potential search query "
    "keywords and snippets that can be used to generate the embeddings.\n"
    "Ensure the search terms are as diverse as possible but capture the "
    "essence of the article and are super related to the articles.\n"
    "Don't return any terms if there aren't any terms of relevance.\n"
    "Always return results in valid JSON of the following format\n"
    '{\n  "search_terms": []\n}'
)


class LlmError(RuntimeError):
    """Raised when an OpenAI call fails. Callers treat it as best-effort."""


def embedding_search_enabled() -> bool:
    """True when an OpenAI key is configured (installation-level gate)."""
    return bool(get_settings().openai_api_key)


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_settings().openai_api_key}",
        "Content-Type": "application/json",
    }


async def embed_text(text: str) -> list[float]:
    """Return the embedding vector for ``text`` (``[]`` for blank input).

    Mirrors ``EmbeddingService#get_embedding`` — blank content short-
    circuits to an empty vector so callers can skip the row entirely.
    """
    if not text or not text.strip():
        return []
    settings = get_settings()
    payload = {
        "model": settings.openai_embedding_model,
        "input": text,
        "dimensions": EMBEDDING_DIM,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/v1/embeddings",
                headers=_auth_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        vector = data["data"][0]["embedding"]
        if not isinstance(vector, list):
            raise LlmError("embedding response had no vector")
        return [float(x) for x in vector]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise LlmError(f"embedding failed: {exc}") from exc


async def generate_search_terms(
    *, title: str, description: str | None, content: str | None
) -> list[str]:
    """Expand an article into diverse search terms via the chat model.

    Mirrors ``generate_article_search_terms``: a JSON-mode ``gpt-4o``
    completion returning ``{"search_terms": [...]}``. Returns ``[]`` on a
    malformed/empty response rather than raising, so indexing a quirky
    article never hard-fails.
    """
    settings = get_settings()
    user_content = (
        f"title: {title} \n description: {description or ''} \n "
        f"content: {content or ''}"
    )
    payload = {
        "model": settings.openai_chat_model,
        "messages": [
            {"role": "system", "content": _SEARCH_TERMS_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/v1/chat/completions",
                headers=_auth_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        raw = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw)
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise LlmError(f"search-term generation failed: {exc}") from exc
    terms = parsed.get("search_terms") if isinstance(parsed, dict) else None
    if not isinstance(terms, list):
        return []
    return [str(t).strip() for t in terms if str(t).strip()]


async def chat_completion(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
) -> dict[str, Any]:
    """One step of the agent chat: the assistant message the model returns,
    with ``content`` and, when it wants to run tools, ``tool_calls``.

    One tool call per step (``parallel_tool_calls: false``) so a write the
    user has to confirm never travels next to another call.
    """
    settings = get_settings()
    payload: dict[str, Any] = {
        "model": settings.openai_agent_model,
        "messages": messages,
        "max_completion_tokens": _CHAT_MAX_COMPLETION_TOKENS,
    }
    if tools:
        payload["tools"] = tools
        payload["parallel_tool_calls"] = False
        if tool_choice:
            payload["tool_choice"] = tool_choice
    try:
        async with httpx.AsyncClient(timeout=_CHAT_TIMEOUT) as client:
            resp = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/v1/chat/completions",
                headers=_auth_headers(),
                json=payload,
            )
            if resp.status_code >= 400:
                raise LlmError(
                    f"chat completion failed: HTTP {resp.status_code} {_error_message(resp)}"
                )
            message = resp.json()["choices"][0]["message"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise LlmError(f"chat completion failed: {exc}") from exc
    if not isinstance(message, dict):
        raise LlmError("chat completion returned no message")
    return message


def _error_message(resp: httpx.Response) -> str:
    """OpenAI's own explanation of a failed request (never echoes the key)."""
    try:
        return str(resp.json()["error"]["message"])[:300]
    except (ValueError, KeyError, TypeError):
        return resp.text[:300]


__all__ = [
    "EMBEDDING_DIM",
    "LlmError",
    "chat_completion",
    "embed_text",
    "embedding_search_enabled",
    "generate_search_terms",
]
