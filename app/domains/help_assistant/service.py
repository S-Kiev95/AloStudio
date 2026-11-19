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

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import llm, local_llm
from app.core.config import get_settings
from app.domains.accounts.models import Account
from app.domains.help_assistant import knowledge
from app.domains.help_assistant.screens import SCREENS
from app.domains.usage.ai import ai_budget_reached, ai_usage

log = logging.getLogger(__name__)

QUESTION_MAX = 300
# Room for the longest answer the grammar allows, in tokens.
MAX_TOKENS = 220
DONT_KNOW = "No lo encuentro en la ayuda de AloStudio. Preguntale a un administrador de tu cuenta."
ADMIN_NOTE = "Esa pantalla la usa un administrador de la cuenta."


# Free: the local model (no cost, ~20 s). Fast: OpenAI (1 to 3 s, recorded in
# the account's AI spend), only when an administrator allowed it.
FREE, FAST = "free", "fast"
PURPOSE = "help_assistant"


def fast_possible() -> bool:
    return bool(get_settings().openai_api_key)


def fast_allowed(account: Account) -> bool:
    return bool(((account.settings or {}).get("help_assistant") or {}).get("fast"))


def modes(account: Account) -> list[str]:
    """What this account can use, Free first."""
    out = []
    if local_llm.configured():
        out.append(FREE)
    if fast_possible() and fast_allowed(account):
        out.append(FAST)
    return out


def enabled(account: Account | None = None) -> bool:
    return bool(modes(account)) if account is not None else local_llm.configured()


def allow_fast(account: Account, allowed: bool) -> None:
    """An administrator lets the account spend on Fast (or stops it)."""
    settings = dict(account.settings or {})
    settings["help_assistant"] = {**(settings.get("help_assistant") or {}), "fast": allowed}
    account.settings = settings


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


async def ask(
    question: str,
    *,
    page: str | None = None,
    is_admin: bool = False,
    mode: str = FREE,
    session: AsyncSession | None = None,
    account_id: int | None = None,
) -> dict[str, Any]:
    """Raises ``ValueError`` (``question``, ``budget``),
    :class:`local_llm.LocalLlmError` (Free) or :class:`llm.LlmError` (Fast)
    when the model cannot answer. Fast needs ``session`` and ``account_id``
    to record the spend."""
    text = " ".join((question or "").split())[:QUESTION_MAX]
    if not text:
        raise ValueError("question")
    started = time.monotonic()
    messages = [
        *knowledge.prefix_messages(),
        {"role": "user", "content": _question(text, page)},
    ]
    if mode == FAST:
        reply = await _ask_openai(messages, session, account_id)
    else:
        raw, timings = await local_llm.chat(
            messages,
            max_tokens=MAX_TOKENS,
            json_schema=knowledge.response_schema(),
            slot=local_llm.HELP_SLOT,
        )
        reply = local_llm.parse_json(raw)
        log.info(
            "help_assistant.local cached=%s read=%s written=%s",
            timings.get("cache_n"),
            timings.get("prompt_n"),
            timings.get("predicted_n"),
        )
    seconds = round(time.monotonic() - started, 1)
    log.info("help_assistant.answered mode=%s seconds=%s sabe=%s", mode, seconds, reply.get("sabe"))
    answer = str(reply.get("respuesta") or "").strip()[: knowledge.ANSWER_MAX]
    if not reply.get("sabe") or not answer:
        return _dont_know(seconds)
    invented = knowledge.invented_menus(answer) + knowledge.invented_quotes(answer)
    if invented:
        log.warning("help_assistant.invented %s", invented)
        return _dont_know(seconds)
    key = reply.get("pantalla")
    screen = SCREENS.get(key) if isinstance(key, str) else None
    out: dict[str, Any] = {
        "known": True,
        "answer": answer,
        "screen": None,
        "note": None,
        "seconds": seconds,
        "mode": mode,
    }
    if screen is not None:
        if screen.admin and not is_admin:
            out["note"] = ADMIN_NOTE
        else:
            out["screen"] = {"key": key, "label": screen.label, "path": screen.path}
    return out


def _dont_know(seconds: float) -> dict[str, Any]:
    return {"known": False, "answer": DONT_KNOW, "screen": None, "note": None, "seconds": seconds}


async def _ask_openai(
    messages: list[dict[str, str]], session: AsyncSession | None, account_id: int | None
) -> dict[str, Any]:
    """The same question to OpenAI, with the same help, rules and checks.
    OpenAI's strict schemas take no ``anyOf`` at the top, so "I don't know"
    is ``sabe: false`` with the other fields empty."""
    if session is None or account_id is None:
        raise ValueError("fast")
    with ai_usage(session, account_id, PURPOSE):
        if await ai_budget_reached():
            raise ValueError("budget")
        message = await llm.chat_completion(
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "ayuda", "strict": True, "schema": _OPENAI_SCHEMA},
            },
        )
    return local_llm.parse_json(str(message.get("content") or ""))


_OPENAI_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sabe": {"type": "boolean"},
        "respuesta": {"type": "string"},
        "pantalla": {"type": "string", "enum": [*SCREENS, knowledge.NO_SCREEN]},
    },
    "required": ["sabe", "respuesta", "pantalla"],
    "additionalProperties": False,
}


async def warm() -> bool:
    """Read the fixed beginning so the first real question does not have to
    (after a restart, or after someone else used the model). Cheap when it
    is already cached: only the probe's few words are new."""
    if not enabled():
        return False
    messages = [*knowledge.prefix_messages(), {"role": "user", "content": "hola"}]
    await local_llm.chat(messages, max_tokens=1, slot=local_llm.HELP_SLOT)
    return True


__all__ = [
    "DONT_KNOW",
    "FAST",
    "FREE",
    "QUESTION_MAX",
    "allow_fast",
    "ask",
    "enabled",
    "fast_allowed",
    "fast_possible",
    "modes",
    "screen_for",
    "warm",
]
