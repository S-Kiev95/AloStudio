"""Decisions by the small model running next to AloStudio (F10).

Qwen (:mod:`app.core.local_llm`) instead of the decisions service: free and
slower (about a minute a conversation on a 4-core VPS). Unlike the service,
it reads what the account says about its business and today's date, so a
seasonal rule holds ("in November and December, enrolling for next year is
urgent"). A grammar forces the answer: one of the options per question, and
a short reason that goes into the conversation when it sets the priority.

It works in its own slot of llama-server, so the help assistant keeps its
long prompt read in the other (a server with one slot is refused at once:
the request would wait behind the help), and one conversation at a time:
while one is being decided the next gets ``busy`` and the worker tries it
again later, instead of holding a worker slot while it waits.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.core import local_llm
from app.core.config import get_settings
from app.domains.decisions.client import Answer, Decisions, DecisionsError

REASON_MAX = 120
MAX_TOKENS = 200
CONTEXT_MAX = 2000
# The reason's field. A question's key is lowercase (``questions.slug``), so
# it can never be called this.
REASON_KEY = "Motivo"

_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

_deciding = asyncio.Lock()


def configured() -> bool:
    return local_llm.configured()


def model_name() -> str:
    return get_settings().local_llm_model or "local"


def today_text(moment: datetime) -> str:
    return f"{_WEEKDAYS[moment.weekday()]} {moment.day} de {_MONTHS[moment.month - 1]} de {moment.year}"


def _system(context: str, questions: dict[str, dict[str, Any]]) -> str:
    """Always the same for an account, so llama-server keeps it read."""
    lines = [
        "Clasificás conversaciones de atención al cliente de un negocio.",
        "Para cada pregunta elegí la opción que mejor describe la conversación. "
        "La descripción de cada opción es la regla del negocio: seguila.",
        f'En "{REASON_KEY}" decí en pocas palabras por qué elegiste la urgencia, '
        "sin nombres ni datos del cliente.",
    ]
    if context:
        lines += ["", "Lo que tenés que saber del negocio:", context]
    for key, question in questions.items():
        lines += ["", f"Pregunta {key}: {question['instructions']}"]
        lines += [f"- {option}: {text}" for option, text in question["criteria"].items()]
    return "\n".join(lines)


def _schema(questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    properties: dict[str, Any] = {
        key: {"type": "string", "enum": list(question["criteria"])}
        for key, question in questions.items()
    }
    properties[REASON_KEY] = {"type": "string", "maxLength": REASON_MAX}
    return {
        "type": "object",
        "properties": properties,
        "required": [*questions, REASON_KEY],
        "additionalProperties": False,
    }


async def ask(
    state: str, questions: dict[str, dict[str, Any]], *, context: str, today: str
) -> Decisions:
    """The model's pick per question, with its reason. Same contract as
    :func:`app.domains.decisions.client.ask` (raises :class:`DecisionsError`)."""
    if not configured():
        raise DecisionsError("not_configured")
    if await local_llm.slot_count() < 2:
        raise DecisionsError("one_slot")
    # Checked and taken with no await in between: one at a time.
    if _deciding.locked():
        raise DecisionsError("busy")
    messages = [
        {"role": "system", "content": _system(context[:CONTEXT_MAX], questions)},
        {"role": "user", "content": f"Hoy es {today}.\n\nConversación:\n{state}"},
    ]
    try:
        async with _deciding:
            raw, timings = await local_llm.chat(
                messages,
                max_tokens=MAX_TOKENS,
                json_schema=_schema(questions),
                slot=local_llm.DECISIONS_SLOT,
            )
        reply = local_llm.parse_json(raw)
    except local_llm.LocalLlmError as exc:
        code = "unreachable" if exc.code in ("unreachable", "timeout") else "refused"
        raise DecisionsError(code, str(exc)) from exc
    return Decisions(
        model=model_name(),
        answers={
            key: Answer(choice=reply[key], confidence=None, probabilities={})
            for key, question in questions.items()
            if isinstance(reply.get(key), str) and reply[key] in question["criteria"]
        },
        input_tokens=int(timings.get("prompt_n") or 0) + int(timings.get("cache_n") or 0),
        output_tokens=int(timings.get("predicted_n") or 0),
        reason=" ".join(str(reply.get(REASON_KEY) or "").split())[:REASON_MAX],
    )


__all__ = ["CONTEXT_MAX", "REASON_KEY", "ask", "configured", "model_name", "today_text"]
