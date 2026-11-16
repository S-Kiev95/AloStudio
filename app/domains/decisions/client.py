"""The decisions service's API (F10): ``POST /v1/systemone``.

TypeSafe's Jev answers it at ``https://api.typesafe.ai``; Laya's ``laya-serve``
answers the same request locally. Which one is used is installation
configuration (``DECISIONS_API_URL`` / ``_KEY`` / ``_MODEL``), not code.

Docs: https://docs.typesafe.ai/introduction/quickstart.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30.0


class DecisionsError(Exception):
    """``not_configured`` (no service set up), ``unreachable``, ``refused``
    (the service said no; its reason in ``detail``)."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class Answer:
    choice: str
    confidence: float | None
    probabilities: dict[str, float]


@dataclass
class Decisions:
    model: str | None
    answers: dict[str, Answer] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0


def configured() -> bool:
    settings = get_settings()
    return bool(settings.decisions_api_url and settings.decisions_api_key)


def _floats(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, prob in value.items():
        try:
            out[str(key)] = float(prob)
        except (TypeError, ValueError):
            continue
    return out


def parse(body: Any) -> Decisions:
    """The service's answer → :class:`Decisions` (choice questions only)."""
    if not isinstance(body, dict):
        raise DecisionsError("refused", "unexpected answer")
    answers: dict[str, Answer] = {}
    raw = body.get("answers")
    for key, value in (raw.items() if isinstance(raw, dict) else []):
        if not isinstance(value, dict) or value.get("choice") is None:
            continue
        confidence = value.get("confidence")
        answers[str(key)] = Answer(
            choice=str(value["choice"]),
            confidence=float(confidence) if isinstance(confidence, int | float) else None,
            probabilities=_floats(value.get("probabilities")),
        )
    raw_usage = body.get("usage")
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    return Decisions(
        model=str(body.get("model")) if body.get("model") else None,
        answers=answers,
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
    )


async def ask(state: str, questions: dict[str, dict[str, Any]]) -> Decisions:
    """Ask the service ``questions`` about ``state`` (already anonymized)."""
    settings = get_settings()
    if not configured():
        raise DecisionsError("not_configured")
    url = settings.decisions_api_url.rstrip("/") + "/v1/systemone"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(
                url,
                json={"state": state, "model": settings.decisions_model, "questions": questions},
                headers={"Authorization": f"Bearer {settings.decisions_api_key}"},
            )
    except httpx.HTTPError as exc:
        raise DecisionsError("unreachable") from exc
    try:
        body = resp.json()
    except ValueError:
        body = None
    if resp.status_code >= 400:
        detail = None
        if isinstance(body, dict):
            error = body.get("error")
            detail = (
                error.get("message") if isinstance(error, dict) else error
            ) or body.get("detail") or body.get("message")
        log.warning("decisions.api_error status=%s body=%s", resp.status_code, resp.text[:300])
        raise DecisionsError("refused", str(detail) if detail else None)
    return parse(body)


__all__ = ["Answer", "Decisions", "DecisionsError", "ask", "configured", "parse"]
