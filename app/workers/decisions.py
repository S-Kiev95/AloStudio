"""ARQ task: decide a conversation (F10).

Enqueued, deferred, when a customer writes; see
:mod:`app.domains.decisions.service`. The conversation is read, then the
session is closed while the service or the model answers (a minute on the
local one), and the answers are stored in a new one. The local model decides
one conversation at a time: the next one is tried again later (ARQ
``Retry``) instead of waiting in a worker slot. If the customer wrote while
it was deciding, it decides again with that.
"""

from __future__ import annotations

import logging
from typing import Any

from app.workers.contact_avatars import _session_factory

log = logging.getLogger(__name__)

# How long a conversation waits when the local model is deciding another,
# and how many tries that gives it (about half an hour on a busy day).
BUSY_RETRY_SECONDS = 60
MAX_TRIES = 30


async def decide_conversation_task(ctx: dict[str, Any], conversation_id: int) -> dict[str, Any]:
    from arq.worker import Retry

    from app.domains.conversations.models import Conversation
    from app.domains.decisions.client import DecisionsError
    from app.domains.decisions.service import (
        ask,
        decide_delay,
        newer_message,
        prepare,
        store,
    )

    factory = _session_factory(ctx)
    async with factory() as session:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            return {"ok": False, "code": "gone"}
        prepared = await prepare(session, conversation)
    if prepared is None:
        return {"ok": True, "decided": 0}
    try:
        result = await ask(prepared)
    except DecisionsError as exc:
        if exc.code == "busy":
            raise Retry(defer=BUSY_RETRY_SECONDS) from exc
        log.warning("decisions.task_failed conversation_id=%s code=%s", conversation_id, exc.code)
        return {"ok": False, "code": exc.code}
    async with factory() as session:
        decided = await store(session, prepared, result)
        await session.commit()
        if await newer_message(session, prepared):
            raise Retry(defer=await decide_delay(session, prepared.account_id))
    return {"ok": True, "decided": len(decided)}


__all__ = ["BUSY_RETRY_SECONDS", "MAX_TRIES", "decide_conversation_task"]
