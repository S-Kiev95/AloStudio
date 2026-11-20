"""The questions an account asks about each conversation (F10).

Each question is a choice among a few options, as the decisions service
expects (``type: choice``, ``criteria: {option: description}``). The
descriptions are what the service reads to decide, so they say plainly what
each option means. The team question takes its options from the account's
teams, so it never goes stale.

Defaults are written for an institute like CTC; each account edits its own.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

MAX_OPTIONS = 12
TEAM_QUESTION = "team"
NO_TEAM = "ninguno"
URGENCY_QUESTION = "urgency"
# The urgency options that set a conversation's priority (``apply_priority``).
PRIORITY_BY_URGENCY: dict[str, str] = {
    "baja": "low",
    "media": "medium",
    "alta": "high",
    "urgente": "urgent",
}
URGENCY_BY_PRIORITY: dict[str, str] = {v: k for k, v in PRIORITY_BY_URGENCY.items()}

DEFAULT_QUESTIONS: list[dict[str, Any]] = [
    {
        "key": "intent",
        "enabled": True,
        "instructions": "¿Qué quiere el cliente en esta conversación?",
        "options": [
            {"key": "inscripcion", "description": "Quiere anotarse o inscribirse a un curso"},
            {"key": "precios", "description": "Pregunta precios, cuotas o formas de pago"},
            {"key": "horarios", "description": "Pregunta horarios, fechas, duración o modalidad"},
            {"key": "certificados", "description": "Pide certificados, constancias o notas"},
            {"key": "reclamo", "description": "Se queja o reclama por algo"},
            {"key": "otro", "description": "Otra cosa"},
        ],
    },
    {
        "key": "sentiment",
        "enabled": True,
        "instructions": "¿Cómo se siente el cliente en sus últimos mensajes?",
        "options": [
            {"key": "positivo", "description": "Contento, agradecido o entusiasmado"},
            {"key": "neutral", "description": "Pregunta o informa sin emoción marcada"},
            {"key": "molesto", "description": "Impaciente o disconforme, pero educado"},
            {"key": "enojado", "description": "Enojado, con quejas fuertes o insultos"},
        ],
    },
    {
        "key": "urgency",
        "enabled": True,
        "instructions": "Según las reglas de cada opción, ¿qué prioridad tiene esta conversación?",
        "options": [
            {"key": "baja", "description": "Puede esperar a mañana"},
            {"key": "media", "description": "Conviene responder hoy"},
            {"key": "alta", "description": "Necesita respuesta ya (plazo que vence, problema serio)"},
            {"key": "urgente", "description": "Lo más urgente: hay que responder antes que todo lo demás"},
        ],
    },
    {
        "key": TEAM_QUESTION,
        "enabled": True,
        "instructions": "¿Qué equipo debería atender esta conversación?",
        # Filled from the account's teams when asked.
        "options": [],
    },
]


def slug(text: str) -> str:
    """``"Precios y cuotas"`` → ``"precios_y_cuotas"``: a stable option key."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_")[:60] or "opcion"


def defaults() -> list[dict[str, Any]]:
    return [
        {**q, "options": [dict(o) for o in q["options"]]} for q in DEFAULT_QUESTIONS
    ]


def team_options(teams: list[tuple[int, str, str | None]]) -> list[dict[str, str]]:
    """The team question's options: one per team, plus "nobody in particular"."""
    options = [
        {
            "key": f"team_{team_id}",
            "description": f"{name}: {description}" if description else name,
        }
        for team_id, name, description in teams
    ]
    if options:
        options.append({"key": NO_TEAM, "description": "Ningún equipo en particular"})
    return options


def clean(questions: Any) -> list[dict[str, Any]]:
    """Validate what the panel sends. Raises ValueError with a short code."""
    if not isinstance(questions, list):
        raise ValueError("questions")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for q in questions:
        if not isinstance(q, dict):
            raise ValueError("questions")
        key = slug(str(q.get("key") or ""))
        if key in seen:
            raise ValueError("duplicate_question")
        seen.add(key)
        instructions = str(q.get("instructions") or "").strip()
        if not instructions:
            raise ValueError("instructions")
        options: list[dict[str, str]] = []
        if key != TEAM_QUESTION:
            raw = q.get("options")
            if not isinstance(raw, list):
                raise ValueError("options")
            keys: set[str] = set()
            for o in raw:
                if not isinstance(o, dict):
                    raise ValueError("options")
                description = str(o.get("description") or "").strip()
                if not description:
                    continue
                option_key = slug(str(o.get("key") or description))
                if option_key in keys:
                    raise ValueError("duplicate_option")
                keys.add(option_key)
                options.append({"key": option_key, "description": description[:300]})
            if not 2 <= len(options) <= MAX_OPTIONS:
                raise ValueError("option_count")
        out.append(
            {
                "key": key,
                "enabled": bool(q.get("enabled", True)),
                "instructions": instructions[:300],
                "options": options,
            }
        )
    return out


def as_service_questions(questions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The enabled questions in the service's shape. A question with fewer
    than two options (a team question without teams) is left out."""
    return {
        q["key"]: {
            "type": "choice",
            "instructions": q["instructions"],
            "criteria": {o["key"]: o["description"] for o in q["options"]},
        }
        for q in questions
        if q.get("enabled") and len(q.get("options") or []) >= 2
    }


__all__ = [
    "DEFAULT_QUESTIONS",
    "MAX_OPTIONS",
    "NO_TEAM",
    "PRIORITY_BY_URGENCY",
    "TEAM_QUESTION",
    "URGENCY_BY_PRIORITY",
    "URGENCY_QUESTION",
    "as_service_questions",
    "clean",
    "defaults",
    "slug",
    "team_options",
]
