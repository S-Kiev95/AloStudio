"""The voice process's HTTP side, for the API only (localhost, bearer token).

* ``POST /calls``              — a call the AI answers: Meta's offer and the
  AI's instructions in, our WebRTC answer out (``sdp_answer``)
* ``POST /calls/{id}/end``     — drop a call (Meta ended it, or it failed)
* ``GET  /health``             — calls under way
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.models_registry import import_all_models
from app.voice.bot import VoiceCall, start_call

# The tools write calls, messages and usage: every mapper must be known,
# as in the worker.
import_all_models()

log = logging.getLogger(__name__)

# Each call holds a WebRTC stream and a Gemini Live session.
MAX_CALLS = int(os.environ.get("VOICE_MAX_CALLS", "4"))

app = FastAPI(title="AloStudio voice", docs_url=None, redoc_url=None, openapi_url=None)
_calls: dict[str, VoiceCall] = {}


class CallSpec(BaseModel):
    call_id: int
    provider_call_id: str = Field(min_length=1, max_length=256)
    account_id: int
    sdp_offer: str = Field(min_length=10, max_length=20000)
    instructions: str = Field(min_length=1, max_length=200_000)
    voice: str = Field(min_length=1, max_length=32)
    model: str = Field(min_length=1, max_length=128)


def _auth(authorization: Annotated[str | None, Header()] = None) -> None:
    token = get_settings().voice_service_token
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(given.encode(), token.encode()):
        raise HTTPException(status_code=401)


@app.post("/calls", dependencies=[Depends(_auth)])
async def create_call(spec: CallSpec) -> dict[str, str]:
    if spec.provider_call_id in _calls:
        raise HTTPException(status_code=409)
    if len(_calls) >= MAX_CALLS:
        raise HTTPException(status_code=503)
    call = await start_call(
        provider_call_id=spec.provider_call_id,
        sdp_offer=spec.sdp_offer,
        instructions=spec.instructions,
        voice=spec.voice,
        model=spec.model,
        on_done=lambda: _calls.pop(spec.provider_call_id, None),
    )
    _calls[spec.provider_call_id] = call
    log.info("voice.call.started call_id=%s", spec.call_id)
    return {"sdp_answer": call.sdp_answer}


@app.post("/calls/{provider_call_id}/end", dependencies=[Depends(_auth)])
async def end_call(provider_call_id: str) -> dict[str, bool]:
    call = _calls.get(provider_call_id)
    if call is not None:
        await call.stop()
    return {"ok": call is not None}


@app.get("/health")
async def health() -> dict[str, int]:
    return {"calls": len(_calls), "max_calls": MAX_CALLS}
