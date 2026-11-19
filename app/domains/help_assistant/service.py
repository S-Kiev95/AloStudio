"""AloStudio's help assistant: answers "how do I…?" from AloStudio's own help
with a small local model, and points to the screen.

The model does little and the code around it does the rest:

  * the fixed beginning (rules, screens, help, examples) is read once and
    cached by llama-server (``knowledge.prefix_messages``);
  * the answer's shape is forced by a grammar: ``{"sabe": false}`` or a short
    answer plus one of the real screens;
  * a ``Menu → Item`` the panel does not have, or "I don't know", becomes a
    fixed reply instead of the model's words;
  * a screen only administrators can open is not linked for an agent.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.core import local_llm
from app.domains.help_assistant import knowledge
from app.domains.help_assistant.screens import SCREENS

log = logging.getLogger(__name__)

QUESTION_MAX = 300
# Room for the longest answer the grammar allows, in tokens.
MAX_TOKENS = 220
DONT_KNOW = "No lo encuentro en la ayuda de AloStudio. Preguntale a un administrador de tu cuenta."
ADMIN_NOTE = "Esa pantalla la usa un administrador de la cuenta."


def enabled() -> bool:
    return local_llm.configured()


def screen_for(page: str | None) -> str | None:
    """The screen key of a panel path (``/accounts/1/settings/lifecycle`` →
    ``ajustes_etapas``): the longest path that matches."""
    if not page:
        return None
    parts = page.strip("/").split("/")
    if len(parts) < 2 or parts[0] != "accounts":
        return None
    rest = "/".join(parts[2:])
    best: tuple[int, str] | None = None
    for key, screen in SCREENS.items():
        if rest == screen.path or (screen.path and rest.startswith(screen.path + "/")):
            if best is None or len(screen.path) > best[0]:
                best = (len(screen.path), key)
    return best[1] if best else ("inicio" if rest == "" else None)


def _question(question: str, page: str | None) -> str:
    where = screen_for(page)
    if where is None:
        return question
    return f"Estoy en: {SCREENS[where].label}\n{question}"


async def ask(question: str, *, page: str | None = None, is_admin: bool = False) -> dict[str, Any]:
    """Raises ``ValueError("question")`` for an empty question and
    :class:`local_llm.LocalLlmError` when the model cannot answer."""
    text = " ".join((question or "").split())[:QUESTION_MAX]
    if not text:
        raise ValueError("question")
    started = time.monotonic()
    messages = [
        *knowledge.prefix_messages(),
        {"role": "user", "content": _question(text, page)},
    ]
    raw, timings = await local_llm.chat(
        messages, max_tokens=MAX_TOKENS, json_schema=knowledge.response_schema()
    )
    reply = local_llm.parse_json(raw)
    seconds = round(time.monotonic() - started, 1)
    log.info(
        "help_assistant.answered seconds=%s cached=%s read=%s written=%s sabe=%s",
        seconds,
        timings.get("cache_n"),
        timings.get("prompt_n"),
        timings.get("predicted_n"),
        reply.get("sabe"),
    )
    answer = str(reply.get("respuesta") or "").strip()
    if not reply.get("sabe") or not answer:
        return _dont_know(seconds)
    invented = knowledge.invented_menus(answer)
    if invented:
        log.warning("help_assistant.invented_menus %s", invented)
        return _dont_know(seconds)
    key = reply.get("pantalla")
    screen = SCREENS.get(key) if isinstance(key, str) else None
    out: dict[str, Any] = {
        "known": True,
        "answer": answer,
        "screen": None,
        "note": None,
        "seconds": seconds,
    }
    if screen is not None:
        if screen.admin and not is_admin:
            out["note"] = ADMIN_NOTE
        else:
            out["screen"] = {"key": key, "label": screen.label, "path": screen.path}
    return out


def _dont_know(seconds: float) -> dict[str, Any]:
    return {"known": False, "answer": DONT_KNOW, "screen": None, "note": None, "seconds": seconds}


async def warm() -> bool:
    """Read the fixed beginning so the first real question does not have to
    (after a restart, or after someone else used the model). Cheap when it
    is already cached: only the probe's few words are new."""
    if not enabled():
        return False
    messages = [*knowledge.prefix_messages(), {"role": "user", "content": "hola"}]
    await local_llm.chat(messages, max_tokens=1)
    return True


__all__ = ["DONT_KNOW", "QUESTION_MAX", "ask", "enabled", "screen_for", "warm"]
