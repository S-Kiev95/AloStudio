"""Decisions by the small model running next to AloStudio (F10).

Qwen (:mod:`app.core.local_llm`) instead of the decisions service: free and
slower (10 to 30 seconds a conversation on a 4-core VPS; the first one, up to
a minute, reads the rules). Unlike the service, it reads what the account
says about its business and today's date, so a seasonal rule holds ("in
November and December, enrolling for next year is urgent"). A grammar forces
the answer: first a short reason (what the customer wants: having said it,
the model picks better; it goes into the conversation when it sets the
priority), then one of the options per question.

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
from app.domains.conversations.models import conversation_priority_from_str
from app.domains.decisions.anonymize import anonymize
from app.domains.decisions.client import Answer, Decisions, DecisionsError
from app.domains.decisions.questions import PRIORITY_BY_URGENCY, URGENCY_QUESTION

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
        f'Primero, en "{REASON_KEY}", decí en una frase corta (menos de 15 palabras) '
        "qué pide el cliente y qué regla aplica, sin nombres ni datos del cliente. "
        "Después elegí las opciones.",
    ]
    if context:
        lines += ["", "Lo que tenés que saber del negocio:", context]
    for key, question in questions.items():
        lines += ["", f"Pregunta {key}: {question['instructions']}"]
        lines += [f"- {option}: {text}" for option, text in _listed(key, question["criteria"])]
    return "\n".join(lines)


def _listed(key: str, criteria: dict[str, str]) -> list[tuple[str, str]]:
    """The options as the model reads them. The urgency's go from the most to
    the least urgent: listed the other way, it hardly ever picked the top one.
    Those that set no priority go after them, in their order."""
    options = list(criteria.items())
    if key != URGENCY_QUESTION:
        return options

    def rank(option: tuple[str, str]) -> int:
        level = conversation_priority_from_str(PRIORITY_BY_URGENCY.get(option[0]))
        return -level if level is not None else 1

    return sorted(options, key=rank)


def _schema(questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    # The reason first (the grammar writes the keys in this order): having
    # said what the customer wants, the model picks better, and writes less.
    properties: dict[str, Any] = {REASON_KEY: {"type": "string", "maxLength": REASON_MAX}}
    for key, question in questions.items():
        properties[key] = {"type": "string", "enum": list(question["criteria"])}
    return {
        "type": "object",
        "properties": properties,
        "required": [REASON_KEY, *questions],
        "additionalProperties": False,
    }


def _reason(raw: Any) -> str:
    """On one line. The grammar stops it at ``REASON_MAX``, maybe in the
    middle of a word (and the model squeezes a stray character in, even a
    Chinese one): back to the last whole word. Long numbers, emails and links
    come out first, so a phone the cut shortens is still caught (the names
    come out in ``service.store``)."""
    text = str(raw or "")
    cut = len(text) >= REASON_MAX
    text = " ".join(anonymize(text).split())
    if not cut:
        return text
    head, space, _ = text.rpartition(" ")
    if not space:
        head = text[: REASON_MAX - 1]
    return head.rstrip(",;:. ") + "…"


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
                # The same conversation, the same pick: the priority does not
                # go back and forth each time the customer writes.
                temperature=0.0,
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
        reason=_reason(reply.get(REASON_KEY)),
    )


__all__ = ["CONTEXT_MAX", "REASON_KEY", "ask", "configured", "model_name", "today_text"]
