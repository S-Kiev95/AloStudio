"""ARQ task: decide a conversation in shadow mode (F10).

Enqueued, deferred, when a customer writes; see
:mod:`app.domains.decisions.service`.
"""

from __future__ import annotations

import logging
from typing import Any

from app.workers.contact_avatars import _session_factory

log = logging.getLogger(__name__)


async def decide_conversation_task(ctx: dict[str, Any], conversation_id: int) -> dict[str, Any]:
    from app.domains.conversations.models import Conversation
    from app.domains.decisions.client import DecisionsError
    from app.domains.decisions.service import decide

    async with _session_factory(ctx)() as session:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            return {"ok": False, "code": "gone"}
        try:
            decided = await decide(session, conversation)
        except DecisionsError as exc:
            log.warning(
                "decisions.task_failed conversation_id=%s code=%s", conversation_id, exc.code
            )
            return {"ok": False, "code": exc.code}
        await session.commit()
    return {"ok": True, "decided": len(decided)}


__all__ = ["decide_conversation_task"]
