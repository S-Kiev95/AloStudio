"""Which embedding model an account uses, and the client for the local one.

Two providers live side by side during the F9 migration:

* ``openai`` — ``text-embedding-3-small`` through :mod:`app.core.llm`,
  stored in the ``vector(1536)`` columns.
* ``gemma`` — EmbeddingGemma 2, served by :mod:`app.embeddings_service` (a
  separate process on localhost), stored in the ``embedding_gemma
  vector(768)`` columns.

Every save writes the vector of each configured provider; which one is
*read* is decided per account (``accounts.internal_attributes
["embedding_read_model"]``, falling back to ``settings.embedding_read_model``).
The two produce distances on different scales, so thresholds are per model
too — see :mod:`app.domains.instagram.autoreply_models`.

The local model needs a short task prefix on every text; the service adds
it from the ``task`` sent here, so callers never build prompts by hand.
"""

from __future__ import annotations

from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.llm import LlmError, embedding_search_enabled

MODEL_OPENAI = "openai"
MODEL_GEMMA = "gemma"
EMBEDDING_MODELS = (MODEL_OPENAI, MODEL_GEMMA)

# Must match the ``vector(768)`` columns. EmbeddingGemma 2's native size.
GEMMA_DIM = 768

# Task types understood by the service. Symmetric comparison (a comment
# against an example question) uses ``classification`` on both sides — it
# separated paraphrases from different questions best in the measurement;
# search uses ``query`` for what a person typed and ``document`` for what
# is being searched.
TASK_CLASSIFICATION = "classification"
TASK_QUERY = "query"
TASK_DOCUMENT = "document"

READ_MODEL_KEY = "embedding_read_model"


class EmbeddingServiceError(LlmError):
    """The local embeddings service failed or is unreachable.

    A subclass of :class:`LlmError` so every caller that already degrades
    on an OpenAI failure (ILIKE fallback, "stay quiet") degrades the same
    way here."""


def gemma_enabled() -> bool:
    """True when the local embeddings service is configured."""
    return bool(get_settings().embeddings_service_url)


def provider_enabled(model: str) -> bool:
    if model == MODEL_GEMMA:
        return gemma_enabled()
    return embedding_search_enabled()


def any_provider_enabled() -> bool:
    return gemma_enabled() or embedding_search_enabled()


def read_model_from(internal_attributes: dict[str, Any] | None) -> str:
    """The model an account reads with, given its ``internal_attributes``."""
    value = (internal_attributes or {}).get(READ_MODEL_KEY)
    if value in EMBEDDING_MODELS:
        return str(value)
    return get_settings().embedding_read_model


async def account_read_model(session: AsyncSession, account_id: int) -> str:
    from app.domains.accounts.models import Account

    account = await session.get(Account, account_id)
    return read_model_from(account.internal_attributes if account else None)


async def embed_gemma(
    texts: list[str],
    *,
    task: str,
    titles: list[str | None] | None = None,
) -> list[list[float]]:
    """Embed ``texts`` with the local model. One vector per text, unit length.

    ``titles`` only matters for ``document``: the model expects
    ``title: … | text: …`` and does better when a real title is given.
    """
    if not texts:
        return []
    settings = get_settings()
    inputs: list[dict[str, Any]] = [
        {"text": text, "title": (titles[i] if titles else None)}
        for i, text in enumerate(texts)
    ]
    try:
        async with httpx.AsyncClient(
            timeout=settings.embeddings_service_timeout
        ) as client:
            resp = await client.post(
                f"{settings.embeddings_service_url.rstrip('/')}/embed",
                json={"task": task, "inputs": inputs},
            )
            resp.raise_for_status()
            vectors = resp.json()["vectors"]
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        raise EmbeddingServiceError(f"local embedding failed: {exc}") from exc
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise EmbeddingServiceError("local embedding returned the wrong count")
    return [[float(x) for x in v] for v in vectors]


async def embed_gemma_one(
    text: str, *, task: str, title: str | None = None
) -> list[float]:
    """Single-text convenience; ``[]`` for blank input, like ``embed_text``."""
    if not text or not text.strip():
        return []
    return (await embed_gemma([text], task=task, titles=[title]))[0]


__all__ = [
    "EMBEDDING_MODELS",
    "GEMMA_DIM",
    "MODEL_GEMMA",
    "MODEL_OPENAI",
    "READ_MODEL_KEY",
    "TASK_CLASSIFICATION",
    "TASK_DOCUMENT",
    "TASK_QUERY",
    "EmbeddingServiceError",
    "account_read_model",
    "any_provider_enabled",
    "embed_gemma",
    "embed_gemma_one",
    "gemma_enabled",
    "provider_enabled",
    "read_model_from",
]
