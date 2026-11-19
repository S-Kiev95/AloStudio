"""What the help assistant knows, and the fixed beginning of every request.

The beginning (rules, the screen list, the whole help and a few examples)
never changes between questions, so llama-server reads it once and reuses
it; each question only adds its own words. Keep ``ayuda.md`` short: every
word is read by a small model on a CPU.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass
from functools import cache
from typing import Any

from app.domains.help_assistant.screens import SCREENS

HELP_FILE = pathlib.Path(__file__).with_name("ayuda.md")
NO_SCREEN = "ninguna"
ANSWER_MAX = 400


@dataclass(frozen=True, slots=True)
class Section:
    title: str
    screens: tuple[str, ...]
    text: str


@cache
def sections() -> tuple[Section, ...]:
    """``## Title`` / ``pantallas: a, b`` / text, from ``ayuda.md``."""
    found: list[Section] = []
    for block in HELP_FILE.read_text(encoding="utf-8").split("\n## ")[1:]:
        title, _, rest = block.partition("\n")
        first, _, text = rest.partition("\n")
        if not first.startswith("pantallas:"):
            raise ValueError(f"help section {title!r} has no 'pantallas:' line")
        keys = tuple(k.strip() for k in first.removeprefix("pantallas:").split(",") if k.strip())
        unknown = [k for k in keys if k not in SCREENS]
        if unknown:
            raise ValueError(f"help section {title!r} names unknown screens {unknown}")
        found.append(Section(title.strip(), keys, " ".join(text.split())))
    return tuple(found)


_RULES = (
    "Sos el asistente de ayuda de AloStudio, un sistema de atención al cliente. Respondés "
    "dudas sobre cómo usar AloStudio usando solo la AYUDA de abajo.\n"
    "Reglas:\n"
    "- Respuesta corta: 1 a 3 oraciones en español rioplatense (vos), con los pasos en orden.\n"
    "- Nombrá menús y botones exactamente como en la AYUDA, con → entre menús.\n"
    "- Si la AYUDA no dice cómo hacerlo, o la duda no es sobre AloStudio, respondé "
    '{"sabe": false}. No inventes menús, botones ni funciones.\n'
    '- "pantalla" es la clave adonde hay que ir, de la lista PANTALLAS, o "ninguna".\n'
    '- Si la persona dice en qué pantalla está ("Estoy en: …"), usalo para entender la duda.'
)

# Fixed examples: they teach the shape and the "I don't know". They are not
# in the evaluation set (``ops/llm/casos_ayuda.json``).
_EXAMPLES: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "¿Cómo le escribo algo a un compañero sin que lo vea el cliente?",
        {
            "sabe": True,
            "respuesta": "Tocá Nota privada abajo de la caja de texto, escribí y enviá: "
            "solo la ve el equipo. Tocalo de nuevo para volver a responderle al cliente.",
            "pantalla": "bandeja",
        },
    ),
    ("¿Cómo conecto AloStudio con Salesforce?", {"sabe": False}),
    (
        "quiero que mis tareas me aparezcan en el calendario de google",
        {
            "sabe": True,
            "respuesta": 'Entrá a Ajustes → Mi perfil y tocá "Conectar Google Calendar". '
            "Tus tareas con fecha y tus citas aparecen en tu calendario cada 5 minutos.",
            "pantalla": "ajustes_perfil",
        },
    ),
)


@cache
def system_prompt() -> str:
    screens = "\n".join(f"{key}: {screen.label}" for key, screen in SCREENS.items())
    help_text = "\n".join(f"## {s.title}\n{s.text}" for s in sections())
    return f"{_RULES}\n\nPANTALLAS:\n{screens}\n\nAYUDA:\n{help_text}"


def prefix_messages() -> list[dict[str, str]]:
    """Everything before the question: always the same, so it is cached."""
    messages = [{"role": "system", "content": system_prompt()}]
    for question, answer in _EXAMPLES:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)})
    return messages


@cache
def response_schema() -> dict[str, Any]:
    """Either ``{"sabe": false}`` (a few tokens, so "I don't know" is quick)
    or an answer with one of the real screens."""
    return {
        "anyOf": [
            {
                "type": "object",
                "properties": {"sabe": {"const": False}},
                "required": ["sabe"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "sabe": {"const": True},
                    "respuesta": {"type": "string", "minLength": 10, "maxLength": ANSWER_MAX},
                    "pantalla": {"enum": [*SCREENS, NO_SCREEN]},
                },
                "required": ["sabe", "respuesta", "pantalla"],
                "additionalProperties": False,
            },
        ]
    }


@cache
def _menus() -> dict[str, tuple[str, ...]]:
    """``{"Ajustes": ("Agentes", …), "CRM": (…)}``: what each top menu holds."""
    menus: dict[str, list[str]] = {}
    for screen in SCREENS.values():
        if " → " in screen.label:
            top, sub = screen.label.split(" → ", 1)
            menus.setdefault(top, []).append(sub)
    return {top: tuple(subs) for top, subs in menus.items()}


def invented_menus(answer: str) -> list[str]:
    """The ``Menu → Item`` paths in ``answer`` that AloStudio does not have."""
    menus = _menus()
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, menus)) + r")\s*→\s*([^\n.,;:()]+)")
    bad = []
    for match in pattern.finditer(answer):
        top, tail = match.group(1), match.group(2).strip().strip("\"'“”«»")
        if not any(tail.startswith(item) for item in menus[top]):
            bad.append(f"{top} → {tail}")
    return bad


__all__ = [
    "ANSWER_MAX",
    "NO_SCREEN",
    "Section",
    "invented_menus",
    "prefix_messages",
    "response_schema",
    "sections",
    "system_prompt",
]
