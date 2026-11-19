"""A contact's first message puts them in the default stage (F17)."""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations import events as ev
from app.domains.conversations.models import MESSAGE_TYPE_INCOMING, Conversation, Message

log = logging.getLogger(__name__)


async def fan_out_to_lifecycle(session: AsyncSession, name: str, **payload: Any) -> None:
    if name != ev.MESSAGE_CREATED:
        return
    message = payload.get("message")
    if not isinstance(message, Message):
        return
    if message.message_type != MESSAGE_TYPE_INCOMING or message.private:
        return
    conversation = await session.get(Conversation, message.conversation_id)
    if conversation is None or not conversation.contact_id:
        return
    from app.domains.lifecycle.models import LifecycleSettings
    from app.domains.lifecycle.service import on_first_message

    settings = await session.get(LifecycleSettings, conversation.account_id)
    if settings is None or not settings.enabled:
        return
    # Two messages at once from a new contact must not both insert: the
    # loser's conflict stays inside this savepoint, not in the message's
    # transaction.
    async with session.begin_nested():
        await on_first_message(
            session, account_id=conversation.account_id, contact_id=conversation.contact_id
        )


__all__ = ["fan_out_to_lifecycle"]
