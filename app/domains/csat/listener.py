"""CSAT listener — emits an ``input_csat`` message on resolve.

Subscribes to the dispatcher's :data:`CONVERSATION_RESOLVED` event
and calls :func:`send_csat_message_on_resolve`, which short-circuits
when the inbox doesn't have CSAT enabled or a survey already exists
on the conversation. Mirrors Chatwoot's ``HookListener``-driven
:class:`MessageTemplates::Template::CsatSurvey` trigger.

The listener is wired into :func:`app.domains.conversations.listeners.broadcast_event`
in the same fan-out as the automation listener (6.4). Failure
isolation: errors are caught + logged so a missing CSAT config can
never break the resolve cycle.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations import events as ev
from app.domains.conversations.models import Conversation
from app.domains.csat.service import send_csat_message_on_resolve

log = logging.getLogger(__name__)


async def fan_out_to_csat(
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
    try:
        await send_csat_message_on_resolve(
            session, conversation=conversation
        )
    except Exception:
        log.exception(
            "csat.listener.send_error conversation_id=%s",
            conversation.id,
        )


__all__ = ["fan_out_to_csat"]
