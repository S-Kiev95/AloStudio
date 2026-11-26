"""One call with the voice AI: WebRTC with Meta, Gemini Live, two tools.

Pipecat runs the pipeline (audio from Meta → Gemini Live → audio to Meta).
Gemini hears and speaks natively, so there is no separate speech-to-text or
text-to-speech step. Its tools act through :mod:`app.domains.calls.voice`:

* ``derivar_a_persona`` — the customer wants a person (handoff with notice)
* ``terminar_llamada`` — the conversation is over: hang up after the goodbye

When the call ends, what was said and the tokens it used go back to the
call (:func:`app.domains.calls.voice.ai_call_over`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import LLMRunFrame, MetricsFrame, TranscriptionFrame, TTSTextFrame
from pipecat.metrics.metrics import LLMUsageMetricsData
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import IceServer, SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domains.calls import voice as calls_voice

log = logging.getLogger(__name__)

# Latin American Spanish; the instructions ask for rioplatense.
LANGUAGE = "es-US"
# Let the goodbye finish playing before hanging up.
HANGUP_DELAY_SECONDS = 3.0
# STUN only helps behind NAT; a server with a public IP answers with its own
# address and skips the wait for the STUN reply. ``VOICE_STUN_URLS``
# (comma separated) turns it on, e.g. ``stun:stun.l.google.com:19302``.
ICE_SERVERS = [
    IceServer(urls=url.strip())
    for url in os.environ.get("VOICE_STUN_URLS", "").split(",")
    if url.strip()
]

HANDOFF = FunctionSchema(
    name="derivar_a_persona",
    description=(
        "El cliente pide hablar con una persona, o el tema necesita a alguien del equipo. "
        "Deja la conversación a una persona con el motivo y un resumen."
    ),
    properties={
        "motivo": {"type": "string", "description": "Por qué necesita una persona, en una frase."},
        "resumen": {
            "type": "string",
            "description": "Lo que pidió el cliente y lo que ya se le dijo, en 2 a 4 frases.",
        },
    },
    required=["motivo", "resumen"],
)
HANGUP = FunctionSchema(
    name="terminar_llamada",
    description="La conversación terminó y ya te despediste: corta la llamada.",
    properties={},
    required=[],
)


def whatsapp_sdp(sdp: str) -> str:
    """Meta only takes SHA-256 fingerprints."""
    lines = [
        line
        for line in sdp.splitlines()
        if not (line.startswith("a=fingerprint:") and not line.startswith("a=fingerprint:sha-256"))
    ]
    return "\r\n".join(lines) + "\r\n"


def _kickoff(opening: str) -> str:
    """The turn that starts the call. Without the exact words the model
    answers the note itself ("Entendido…") before greeting (staging,
    2026-11-26)."""
    if not opening:
        return "(La llamada acaba de conectarse. Saludá al cliente.)"
    return (
        "(La llamada acaba de conectarse. Tu primera frase, sin agregar nada antes, es "
        f"exactamente: «{opening}». Después preguntá en qué podés ayudar.)"
    )


class _Notes(BaseObserver):
    """What was said (by turns) and the tokens used."""

    def __init__(self) -> None:
        super().__init__(observe_every_push=False)
        self.segments: list[dict[str, Any]] = []
        self.usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "input_audio_tokens": 0,
            "output_audio_tokens": 0,
        }

    def _say(self, speaker: str, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self.segments and self.segments[-1]["speaker"] == speaker:
            self.segments[-1]["text"] += " " + text
        else:
            self.segments.append({"speaker": speaker, "text": text})

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if isinstance(frame, TranscriptionFrame):
            self._say("customer", frame.text)
        elif isinstance(frame, TTSTextFrame):
            self._say("business", frame.text)
        elif isinstance(frame, MetricsFrame):
            for item in frame.data:
                if isinstance(item, LLMUsageMetricsData):
                    tokens = item.value
                    self.usage["input_tokens"] += tokens.prompt_tokens or 0
                    self.usage["output_tokens"] += tokens.completion_tokens or 0
                    self.usage["cached_tokens"] += tokens.cache_read_input_tokens or 0
                    self.usage["input_audio_tokens"] += tokens.input_audio_tokens or 0
                    self.usage["output_audio_tokens"] += tokens.output_audio_tokens or 0


@dataclass
class VoiceCall:
    provider_call_id: str
    sdp_answer: str
    connection: SmallWebRTCConnection
    worker: PipelineWorker
    runner_task: asyncio.Task[None] | None = None
    background: set[asyncio.Task[Any]] = field(default_factory=set)

    async def stop(self) -> None:
        with contextlib.suppress(Exception):
            await self.worker.cancel()
        with contextlib.suppress(Exception):
            await self.connection.disconnect()


async def _in_session(action: Callable[..., Any], **kwargs: Any) -> Any:
    async with get_session_factory()() as session:
        try:
            result = await action(session, **kwargs)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            log.exception("voice.db_failed action=%s", getattr(action, "__name__", action))
            return None


async def start_call(
    *,
    provider_call_id: str,
    sdp_offer: str,
    instructions: str,
    opening: str,
    voice: str,
    model: str,
    on_done: Callable[[], Any],
) -> VoiceCall:
    """Answer Meta's offer and start talking once the audio connects."""
    connection = SmallWebRTCConnection(ICE_SERVERS)
    await connection.initialize(sdp=sdp_offer, type="offer")
    answer = connection.get_answer() or {}
    sdp_answer = whatsapp_sdp(str(answer.get("sdp") or ""))

    transport = SmallWebRTCTransport(
        connection, TransportParams(audio_in_enabled=True, audio_out_enabled=True)
    )
    llm = GeminiLiveLLMService(
        api_key=get_settings().gemini_api_key,
        settings=GeminiLiveLLMService.Settings(
            model=model if model.startswith("models/") else f"models/{model}",
            voice=voice,
            language=LANGUAGE,
            system_instruction=instructions,
        ),
        tools=ToolsSchema(standard_tools=[HANDOFF, HANGUP]),
    )
    context = LLMContext(messages=[{"role": "user", "content": _kickoff(opening)}])
    aggregators = LLMContextAggregatorPair(context)
    pipeline = Pipeline(
        [transport.input(), aggregators.user(), llm, transport.output(), aggregators.assistant()]
    )
    notes = _Notes()
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        observers=[notes],
    )
    call = VoiceCall(
        provider_call_id=provider_call_id,
        sdp_answer=sdp_answer,
        connection=connection,
        worker=worker,
    )

    async def handoff(params: FunctionCallParams) -> None:
        done = await _in_session(
            calls_voice.ai_handoff,
            provider_call_id=provider_call_id,
            reason=str(params.arguments.get("motivo") or ""),
            summary=str(params.arguments.get("resumen") or ""),
        )
        await params.result_callback({"ok": bool(done)})

    async def hangup(params: FunctionCallParams) -> None:
        await params.result_callback({"ok": True})

        async def later() -> None:
            await asyncio.sleep(HANGUP_DELAY_SECONDS)
            await _in_session(calls_voice.ai_hangup, provider_call_id=provider_call_id)
            await call.stop()

        task = asyncio.create_task(later())
        call.background.add(task)
        task.add_done_callback(call.background.discard)

    llm.register_function("derivar_a_persona", handoff)
    llm.register_function("terminar_llamada", hangup)

    @transport.event_handler("on_client_connected")
    async def _connected(_transport: Any, _client: Any) -> None:
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def _disconnected(_transport: Any, _client: Any) -> None:
        await worker.cancel()

    async def run() -> None:
        try:
            await PipelineRunner(handle_sigint=False).run(worker)
        except Exception:
            log.exception("voice.call.crashed provider_call_id=%s", provider_call_id)
        finally:
            await _in_session(
                calls_voice.ai_call_over,
                provider_call_id=provider_call_id,
                model=model,
                usage=dict(notes.usage),
                segments=list(notes.segments),
            )
            with contextlib.suppress(Exception):
                await connection.disconnect()
            on_done()
            log.info(
                "voice.call.over provider_call_id=%s turns=%s",
                provider_call_id,
                len(notes.segments),
            )

    call.runner_task = asyncio.create_task(run())
    return call
