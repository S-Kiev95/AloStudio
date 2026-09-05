"""Conversation index / search backend.

Ported from:
  reference/chatwoot/app/finders/conversation_finder.rb

Used by ``GET /conversations``, ``GET /conversations/meta`` and
``GET /conversations/search``. The filter-DSL ``POST /conversations/filter``
endpoint goes through :mod:`app.domains.conversations.filter` instead.

Phase 4b subset:
  * ``status`` (default ``open``; ``all`` keeps every status).
  * ``assignee_type`` (``me`` / ``assigned`` / ``unassigned``; default all).
  * ``inbox_id`` (single id, scoped to inboxes the user has access to —
    Phase 4c will gate this behind the proper inbox-membership check;
    for now we use the simpler "in this account" guard).
  * ``team_id`` (single id, scoped to the account).
  * ``labels`` (list of strings — OR semantics, mirrors Rails
    ``tagged_with(labels, any: true)``).
  * ``q`` (free-text search on message content; case-insensitive
    ILIKE; restricted to incoming/outgoing message types).
  * ``page`` (1-based; results-per-page from
    :data:`app.domains.conversations.router.RESULTS_PER_PAGE`).

Deferred (logged here, ports in later phases):
  * ``conversation_type`` (mention / participating / unattended) —
    needs the Mention model + ConversationParticipant queries
    (Phase 9 alongside notifications).
  * ``source_id`` filter — used by widgets to look up by external
    contact id; lands when we ship the front-end widget endpoints.
  * ``updated_within`` — alternative pagination scheme used by mobile
    clients. Trivial to add when needed.
  * ``PermissionFilterService`` — role-based view scoping, Phase 4c.
  * Sort options other than ``last_activity_at_desc``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import lazyload, selectinload
from sqlalchemy.sql import Select
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    ConversationLabel,
    Message,
    conversation_status_from_str,
)
from app.domains.conversations.permission import apply_permission_scope
from app.domains.labels.models import Label

DEFAULT_STATUS = "open"
DEFAULT_PER_PAGE = 25


def _apply_status(stmt: Select, *, status: str | None) -> Select:
    """Mirror ``ConversationFinder#filter_by_status``.

    ``status='all'`` removes the filter, ``None`` defaults to
    ``DEFAULT_STATUS`` (Chatwoot's behaviour).
    """
    if status == "all":
        return stmt
    target = conversation_status_from_str(status or DEFAULT_STATUS)
    return stmt.where(Conversation.status == target)


def _apply_assignee_type(
    stmt: Select, *, assignee_type: str | None, current_user_id: int | None
) -> Select:
    if assignee_type == "me" and current_user_id is not None:
        return stmt.where(Conversation.assignee_id == current_user_id)
    if assignee_type == "assigned":
        return stmt.where(Conversation.assignee_id.is_not(None))
    if assignee_type == "unassigned":
        return stmt.where(Conversation.assignee_id.is_(None))
    return stmt


def _apply_inbox(stmt: Select, *, inbox_id: int | None) -> Select:
    if inbox_id is None:
        return stmt
    return stmt.where(Conversation.inbox_id == inbox_id)


def _apply_team(stmt: Select, *, team_id: int | None) -> Select:
    if team_id is None:
        return stmt
    return stmt.where(Conversation.team_id == team_id)


def _apply_labels(stmt: Select, *, labels: list[str] | None) -> Select:
    """Mirror ``ConversationFinder#filter_by_labels``.

    Rails uses ``tagged_with(labels, any: true)`` — OR semantics — which
    becomes a subquery on (conversation_labels JOIN labels) restricted
    to the requested titles.
    """
    if not labels:
        return stmt
    sub = (
        select(ConversationLabel.conversation_id)
        .join(Label, Label.id == ConversationLabel.label_id)
        .where(Label.title.in_(labels))  # type: ignore[attr-defined]
    )
    return stmt.where(Conversation.id.in_(sub))


def _apply_query(stmt: Select, *, q: str | None) -> Select:
    """Mirror ``ConversationFinder#filter_by_query``.

    ILIKE search on message.content limited to incoming / outgoing
    messages — activity rows + private notes are excluded so a search
    for "alice" doesn't match the activity log "Assigned to alice".
    """
    if not q:
        return stmt
    pattern = f"%{q}%"
    sub = (
        select(Message.conversation_id)
        .where(Message.content.ilike(pattern))
        .where(
            Message.message_type.in_(  # type: ignore[attr-defined]
                [MESSAGE_TYPE_INCOMING, MESSAGE_TYPE_OUTGOING]
            )
        )
    )
    return stmt.where(Conversation.id.in_(sub))


async def conversation_finder(
    session: AsyncSession,
    *,
    account_id: int,
    current_user_id: int,
    params: dict[str, Any],
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> dict[str, Any]:
    """Return ``{'conversations': [...], 'count': {...}}``.

    Mirrors ``ConversationFinder#perform``. The count block is computed
    over the ``status`` + ``inbox`` / ``team`` / ``labels`` / ``q``
    filtered set BEFORE the ``assignee_type`` filter is applied — that
    way ``mine_count`` / ``unassigned_count`` reflect the full visible
    set, exactly as Rails does.

    ``params`` accepts the keys documented in the module docstring;
    everything is optional. Unknown keys are ignored (Rails does the
    same — its ``permit!`` strips nothing).
    """
    status = params.get("status")
    inbox_id = params.get("inbox_id")
    team_id = params.get("team_id")
    labels = params.get("labels")
    q = params.get("q")

    if isinstance(inbox_id, str):
        inbox_id = int(inbox_id) if inbox_id.isdigit() else None
    if isinstance(team_id, str):
        team_id = int(team_id) if team_id.isdigit() else None
    if isinstance(labels, str):
        labels = [labels]
    if labels is not None:
        labels = [str(label) for label in labels if label]

    base = select(Conversation).where(Conversation.account_id == account_id)
    base = await apply_permission_scope(
        base,
        session=session,
        account_id=account_id,
        current_user_id=current_user_id,
    )
    # When ``q`` is set Rails skips the status filter entirely (search
    # spans every status). Match that.
    if not q:
        base = _apply_status(base, status=status)
    base = _apply_inbox(base, inbox_id=inbox_id)
    base = _apply_team(base, team_id=team_id)
    base = _apply_labels(base, labels=labels)
    base = _apply_query(base, q=q)

    # Count block — pre-assignee_type, mirrors Rails ordering. The same
    # permission scope must apply, so non-admins don't see a count of
    # conversations they can't list.
    count_select = (
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.account_id == account_id)
    )
    count_select = await apply_permission_scope(
        count_select,
        session=session,
        account_id=account_id,
        current_user_id=current_user_id,
    )
    if not q:
        count_select = _apply_status(count_select, status=status)
    count_select = _apply_inbox(count_select, inbox_id=inbox_id)
    count_select = _apply_team(count_select, team_id=team_id)
    count_select = _apply_labels(count_select, labels=labels)
    count_select = _apply_query(count_select, q=q)

    all_count = int((await session.exec(count_select)).one() or 0)
    mine_count = int(
        (
            await session.exec(
                count_select.where(Conversation.assignee_id == current_user_id)
            )
        ).one()
        or 0
    )
    unassigned_count = int(
        (
            await session.exec(
                count_select.where(Conversation.assignee_id.is_(None))
            )
        ).one()
        or 0
    )
    assigned_count = all_count - unassigned_count

    # Page through the set after applying assignee_type — Rails uses the
    # finder's ``conversations`` method which sorts last_activity_at desc.
    listed = _apply_assignee_type(
        base, assignee_type=params.get("assignee_type"), current_user_id=current_user_id
    )
    listed = (
        listed.order_by(Conversation.last_activity_at.desc())  # type: ignore[attr-defined]
        .offset((max(page, 1) - 1) * per_page)
        .limit(per_page)
        .options(*_list_loaders())
    )
    rows = list((await session.exec(listed)).all())

    return {
        "conversations": rows,
        "count": {
            "mine_count": mine_count,
            "assigned_count": assigned_count,
            "unassigned_count": unassigned_count,
            "all_count": all_count,
        },
    }


# What ``present_conversation`` actually reads off a row, and nothing else.
#
# Every relationship in this codebase is declared ``lazy="selectin"``, so a
# plain ``select(Conversation)`` pulls a large connected component of the
# schema: measured against staging, one page of 25 emitted **79 queries**
# and ~300 ms, of which 30 were on ``users``, 15 on ``accounts`` and 15 on
# ``account_users`` — none of which appear in the payload. Naming the
# relations here brings it to 8 queries and ~60 ms.
#
# ``lazyload("*")`` turns the eager defaults off for this statement only;
# it does not change the models, so every other query behaves as before.
#
# ``Message.conversation`` is deliberately absent even though
# ``present_message_push_event`` reads it: it is a many-to-one back to a
# row already in the identity map, which SQLAlchemy resolves without
# going to the database.
#
# If the presenter starts reading something new, the count test in
# ``tests/integration/test_conversation_list_queries.py`` fails rather
# than the request quietly costing 79 queries again.
def _list_loaders() -> tuple[Any, ...]:
    return (
        lazyload("*"),
        selectinload(Conversation.contact),
        selectinload(Conversation.inbox),
        selectinload(Conversation.assignee),
        selectinload(Conversation.team),
        selectinload(Conversation.contact_inbox),
        selectinload(Conversation.messages).selectinload(Message.attachments),
    )


__all__ = ["DEFAULT_PER_PAGE", "DEFAULT_STATUS", "conversation_finder"]
