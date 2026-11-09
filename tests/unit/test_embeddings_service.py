"""The local embeddings service and the per-account model choice.

The service is exercised with a fake encoder: what matters here is the
contract (task prefixes, limits, the loaded/not-loaded states), not torch.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.embeddings import READ_MODEL_KEY, read_model_from
from app.embeddings_service.main import EmbedInput, create_app, format_inputs

pytestmark = pytest.mark.unit


def test_documents_get_the_title_format_the_model_expects():
    assert format_inputs(
        "document",
        [EmbedInput(text="Tocá el clip.", title="Adjuntar archivos"), EmbedInput(text="x")],
    ) == [
        "title: Adjuntar archivos | text: Tocá el clip.",
        "title: none | text: x",
    ]


def test_comparisons_and_searches_get_their_task_prefix():
    assert format_inputs("classification", [EmbedInput(text="hay becas?")]) == [
        "task: classification | query: hay becas?"
    ]
    assert format_inputs("query", [EmbedInput(text="como mando un pdf")]) == [
        "task: search result | query: como mando un pdf"
    ]


async def test_the_service_embeds_with_the_prefixed_text():
    seen: list[str] = []

    def encoder(texts: Sequence[str]) -> list[list[float]]:
        seen.extend(texts)
        return [[1.0, 0.0] for _ in texts]

    app = create_app(lambda: encoder)
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            health = await client.get("/health")
            resp = await client.post(
                "/embed",
                json={"task": "classification", "inputs": [{"text": "hola"}]},
            )
    assert health.json()["ok"] is True
    assert resp.status_code == 200
    assert resp.json()["vectors"] == [[1.0, 0.0]]
    assert seen == ["task: classification | query: hola"]


async def test_the_service_refuses_an_unknown_task_or_an_empty_batch():
    app = create_app(lambda: lambda texts: [[0.0] for _ in texts])
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            unknown = await client.post(
                "/embed", json={"task": "chat", "inputs": [{"text": "x"}]}
            )
            empty = await client.post("/embed", json={"task": "query", "inputs": []})
    assert unknown.status_code == 422
    assert empty.status_code == 422


def test_an_account_override_wins_over_the_installation_default():
    assert read_model_from({READ_MODEL_KEY: "gemma"}) == "gemma"
    assert read_model_from({}) == get_settings().embedding_read_model
    assert read_model_from(None) == get_settings().embedding_read_model
    # A typo in the flag must not leave the account on an unknown model.
    assert read_model_from({READ_MODEL_KEY: "gema"}) == get_settings().embedding_read_model
