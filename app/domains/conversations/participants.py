"""Conversation participants — agents "watching" a conversation.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/conversations/participants_controller.rb
  reference/chatwoot/app/models/conversation_participant.rb

A participant is any account user added to a conversation's watcher set
(they receive notifications without being the assignee). The user must
be an *assignable agent* of the conversation's inbox — an inbox member
OR an account administrator (mirrors ``Inbox#assignable_agents``).
``account_id`` is denormalised from the conversation (Rails'
``before_validation :ensure_account_id``).
"""

from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.conversations.models import (
    Conversation,
    ConversationParticipant,
)
from app.domains.inboxes.models import InboxMember
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccountUser,
    User,
)


async def list_participant_users(
    session: AsyncSession, *, conversation_id: int
) -> list[User]:
    """Users participating in the conversation, in join order."""
    stmt = (
        select(User)
        .join(
            ConversationParticipant,
            ConversationParticipant.user_id == User.id,  # type: ignore[arg-type]
        )
        .where(ConversationParticipant.conversation_id == conversation_id)
        .order_by(ConversationParticipant.id.asc())  # type: ignore[attr-defined]
    )
    return list((await session.exec(stmt)).all())


async def _current_participant_ids(
    session: AsyncSession, *, conversation_id: int
) -> set[int]:
    rows = (
        await session.exec(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id
            )
        )
    ).all()
    return set(rows)


async def _assignable_agent_ids(
    session: AsyncSession, *, account_id: int, inbox_id: int
) -> set[int]:
    """``Inbox#assignable_agents`` — inbox members plus account admins."""
    members = (
        await session.exec(
            select(InboxMember.user_id).where(
                InboxMember.inbox_id == inbox_id
            )
        )
    ).all()
    admins = (
        await session.exec(
            select(AccountUser.user_id).where(
                AccountUser.account_id == account_id,
                AccountUser.role == ACCOUNT_USER_ROLE_ADMINISTRATOR,
            )
        )
    ).all()
    return set(members) | set(admins)


def _inbox_access_error() -> ChatwootHTTPException:
    """Rails' ``errors.add(:user, 'must have inbox access')`` → 422."""
    return ChatwootHTTPException(
        status_code=422,
        detail={"message": "User must have inbox access"},
    )


async def add_participants(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_ids: list[int],
) -> None:
    """``find_or_create_by`` each id — new ids must be assignable agents.

    Already-present participants are left untouched (idempotent), so the
    inbox-access check only runs on genuinely new rows.
    """
    existing = await _current_participant_ids(
        session, conversation_id=conversation.id
    )
    to_add = [uid for uid in dict.fromkeys(user_ids) if uid not in existing]
    if not to_add:
        return
    allowed = await _assignable_agent_ids(
        session,
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
    )
    for uid in to_add:
        if uid not in allowed:
            raise _inbox_access_error()
        session.add(
            ConversationParticipant(
                account_id=conversation.account_id,
                conversation_id=conversation.id,
                user_id=uid,
            )
        )
    await session.flush()


async def set_participants(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_ids: list[int],
) -> None:
    """Reconcile the watcher set to exactly ``user_ids`` (add + remove)."""
    current = await _current_participant_ids(
        session, conversation_id=conversation.id
    )
    target = set(user_ids)
    to_add = target - current
    to_remove = current - target
    if to_add:
        allowed = await _assignable_agent_ids(
            session,
            account_id=conversation.account_id,
            inbox_id=conversation.inbox_id,
        )
        for uid in to_add:
            if uid not in allowed:
                raise _inbox_access_error()
            session.add(
                ConversationParticipant(
                    account_id=conversation.account_id,
                    conversation_id=conversation.id,
                    user_id=uid,
                )
            )
    if to_remove:
        await _delete_participants(
            session, conversation_id=conversation.id, user_ids=to_remove
        )
    await session.flush()


async def remove_participants(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_ids: list[int],
) -> None:
    """Drop the given users from the conversation's watcher set."""
    await _delete_participants(
        session, conversation_id=conversation.id, user_ids=set(user_ids)
    )
    await session.flush()


async def _delete_participants(
    session: AsyncSession, *, conversation_id: int, user_ids: set[int]
) -> None:
    if not user_ids:
        return
    rows = (
        await session.exec(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id.in_(user_ids),  # type: ignore[union-attr]
            )
        )
    ).all()
    for row in rows:
        await session.delete(row)


__all__ = [
    "add_participants",
    "list_participant_users",
    "remove_participants",
    "set_participants",
]
