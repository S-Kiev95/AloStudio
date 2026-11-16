"""A customer's message schedules a decision about its conversation (F10)."""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations import events as ev
from app.domains.conversations.models import MESSAGE_TYPE_INCOMING, Message

log = logging.getLogger(__name__)


async def fan_out_to_decisions(session: AsyncSession, name: str, **payload: Any) -> None:
    if name != ev.MESSAGE_CREATED:
        return
    message = payload.get("message")
    if not isinstance(message, Message):
        return
    if message.message_type != MESSAGE_TYPE_INCOMING or message.private or not message.content:
        return
    from app.domains.decisions.service import enqueue_decide, is_on

    if await is_on(session, message.account_id):
        await enqueue_decide(message.conversation_id)


__all__ = ["fan_out_to_decisions"]
