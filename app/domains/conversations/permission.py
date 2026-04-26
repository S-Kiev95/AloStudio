"""Role-based view scoping for conversation lists.

Ported from:
  reference/chatwoot/app/services/conversations/permission_filter_service.rb

Rule:
  * Administrators see every conversation in the account.
  * Agents (any non-administrator role) see only conversations whose
    ``inbox_id`` is in their ``inbox_members`` set for that account.

Rails applies this via ``Conversations::PermissionFilterService.new(
relation, user, account).perform`` — we expose a single
``apply_permission_scope`` helper that mutates a SQLAlchemy ``Select``
in place by adding the ``WHERE inbox_id IN (...)`` clause when the
caller isn't an admin.

Phase 4c only ports the v1 logic. The enterprise branch (custom roles
with per-attribute scope) ships with the role engine in Phase 9.
"""

from __future__ import annotations

from sqlalchemy.sql import Select
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Conversation
from app.domains.inboxes.models import InboxMember
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccountUser,
)


async def is_administrator(
    session: AsyncSession, *, account_id: int, user_id: int
) -> bool:
    """Mirror ``PermissionFilterService#user_role == 'administrator'``.

    Returns False if the user has no AccountUser row for this account
    (defensive — the controller's ``account_context`` dependency should
    have rejected the request earlier, but we don't want a missing row
    to leak data via the admin shortcut).
    """
    row = (
        await session.exec(
            select(AccountUser.role).where(
                AccountUser.account_id == account_id,
                AccountUser.user_id == user_id,
            )
        )
    ).first()
    return row == ACCOUNT_USER_ROLE_ADMINISTRATOR


async def apply_permission_scope(
    stmt: Select,
    *,
    session: AsyncSession,
    account_id: int,
    current_user_id: int,
) -> Select:
    """Add the agent inbox-membership filter when the caller isn't an admin.

    Mirrors ``PermissionFilterService#accessible_conversations``:
      ``conversations.where(inbox: user.inboxes.where(account_id:))``.

    The Rails implementation joins through ``inbox_members`` — we do
    the same with a subquery so the resulting plan can use the
    ``index_inbox_members_on_user_id`` index without forcing a JOIN
    onto every aggregate ``count(*)`` call site.
    """
    if await is_administrator(
        session, account_id=account_id, user_id=current_user_id
    ):
        return stmt

    member_inbox_ids = select(InboxMember.inbox_id).where(
        InboxMember.user_id == current_user_id
    )
    return stmt.where(Conversation.inbox_id.in_(member_inbox_ids))  # type: ignore[attr-defined]


__all__ = ["apply_permission_scope", "is_administrator"]
