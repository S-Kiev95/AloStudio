"""Local embeddings service: EmbeddingGemma 2 behind a tiny HTTP API.

Runs as its own process (``alostudio-embeddings``) so the model's ~2 GB and
~14 s load are paid once, outside the API and the worker, under its own
memory cap. It listens on localhost only and holds no data: text in,
vectors out.

    uvicorn app.embeddings_service.main:app --host 127.0.0.1 --port 8100

Dependencies live in ``app/embeddings_service/requirements.txt`` and are
installed into a separate virtualenv; nothing here imports the rest of the
app, so the main environment never needs torch.

Choices, all from the measurement in docs/experimentos/embeddinggemma.md:

* text-only load (no vision/audio encoders): 271M parameters, ~1.8 GB;
* ``float32``: the VPS CPUs have no native bf16, where ``bfloat16`` is
  2-4x slower (``float16`` is never safe for this model);
* two threads: one text costs ~0.3 s and barely improves with more;
* the task prefix the model was trained with is added here, per ``task``.
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Any, Literal, Protocol

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODEL_NAME = "google/embeddinggemma-2"
DIM = 768
MAX_INPUTS = 64
MAX_CHARS = 20_000

Task = Literal["classification", "query", "document"]

# From the model card ("Task Instruction Prefixes").
_PREFIXES: dict[str, str] = {
    "classification": "task: classification | query: ",
    "query": "task: search result | query: ",
}


class EmbedInput(BaseModel):
    text: str = Field(max_length=MAX_CHARS)
    title: str | None = Field(default=None, max_length=500)


class EmbedRequest(BaseModel):
    task: Task
    inputs: list[EmbedInput] = Field(min_length=1, max_length=MAX_INPUTS)


class Encoder(Protocol):
    def __call__(self, texts: Sequence[str]) -> list[list[float]]: ...


def format_inputs(task: str, inputs: Sequence[EmbedInput]) -> list[str]:
    """The exact strings the model sees.

    Documents are ``title: {title} | text: {text}`` (``title: none`` when
    there is none); everything else gets its task prefix."""
    if task == "document":
        return [
            f"title: {(i.title or '').strip() or 'none'} | text: {i.text}"
            for i in inputs
        ]
    prefix = _PREFIXES[task]
    return [prefix + i.text for i in inputs]


def load_sentence_transformer() -> Encoder:  # pragma: no cover - needs torch
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(int(os.environ.get("EMBEDDINGS_THREADS", "2")))
    model = SentenceTransformer(
        os.environ.get("EMBEDDINGS_MODEL", MODEL_NAME),
        device="cpu",
        model_kwargs={"torch_dtype": torch.float32},
        config_kwargs={"vision_config": None, "audio_config": None},
    )

    def encode(texts: Sequence[str]) -> list[list[float]]:
        vectors = model.encode(
            list(texts),
            batch_size=16,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [[float(x) for x in v] for v in vectors]

    return encode


def create_app(load: Callable[[], Encoder] = load_sentence_transformer) -> FastAPI:
    state: dict[str, Any] = {}
    # One encode at a time: torch already spreads one batch over the
    # threads it has, and two concurrent batches would only double memory.
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        state["encode"] = await asyncio.to_thread(load)
        yield
        state.clear()

    app = FastAPI(title="AloStudio embeddings", lifespan=lifespan)

    def _encode(texts: list[str]) -> list[list[float]]:
        with lock:
            encoder: Encoder = state["encode"]
            return encoder(texts)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": "encode" in state, "model": MODEL_NAME, "dim": DIM}

    @app.post("/embed")
    async def embed(payload: EmbedRequest) -> dict[str, Any]:
        if "encode" not in state:
            raise HTTPException(status_code=503, detail="model not loaded")
        texts = format_inputs(payload.task, payload.inputs)
        vectors = await asyncio.to_thread(_encode, texts)
        return {"model": MODEL_NAME, "dim": DIM, "vectors": vectors}

    return app


app = create_app()
