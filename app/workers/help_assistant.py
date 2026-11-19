"""Keep the help assistant's fixed beginning read in the local model."""

from __future__ import annotations

import logging
from typing import Any

from app.core.local_llm import LocalLlmError

log = logging.getLogger(__name__)


async def warm_help_assistant_task(ctx: dict[str, Any]) -> dict[str, Any]:
    from app.domains.help_assistant.service import warm

    try:
        return {"warmed": await warm()}
    except LocalLlmError as exc:
        log.warning("help_assistant.warm_failed code=%s", exc.code)
        return {"warmed": False, "code": exc.code}


__all__ = ["warm_help_assistant_task"]
