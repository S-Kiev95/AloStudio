"""WhatsApp listener — hands resolved conversations back to the AI.

Subscribes to :data:`CONVERSATION_RESOLVED`: when the team owned a
conversation on a number answered by Meta Business Agent, resolving it
queues a job that returns control to the agent
(:mod:`app.workers.business_agent`; the job also checks
``meta_business_agent_return_on_resolve``). Only a cheap owner check runs
here, so the resolve never waits on Meta. Wired into
:func:`app.domains.conversations.listeners.broadcast_event` next to the
CSAT listener, with the same contract: failures are logged, never raised.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations import events as ev
from app.domains.conversations.models import Conversation

log = logging.getLogger(__name__)


async def fan_out_to_whatsapp(
    session: AsyncSession,
    event_name: str,
    **payload: Any,
) -> None:
    """Single entry point — runs only on ``conversation.resolved``."""
    if event_name != ev.CONVERSATION_RESOLVED:
        return
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return
    from app.domains.whatsapp.business_agent import OWNER_APP, thread_owner
    from app.workers.business_agent import enqueue_release_to_ai

    if conversation.id is None or thread_owner(conversation) != OWNER_APP:
        return
    try:
        await enqueue_release_to_ai(conversation_id=conversation.id)
    except Exception:
        log.exception(
            "whatsapp.listener.release_error conversation_id=%s",
            conversation.id,
        )


__all__ = ["fan_out_to_whatsapp"]
