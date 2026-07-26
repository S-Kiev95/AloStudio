"""Notifications HTTP endpoints.

Ports ``Api::V1::Accounts::NotificationsController`` +
``Api::V1::Accounts::NotificationSettingsController``.

Route map:

  * ``GET    /api/v1/accounts/{id}/notifications``               — list
  * ``GET    /api/v1/accounts/{id}/notifications/unread_count``  — int
  * ``POST   /api/v1/accounts/{id}/notifications/{nid}/read``    — mark one
  * ``POST   /api/v1/accounts/{id}/notifications/read_all``      — mark all
  * ``DELETE /api/v1/accounts/{id}/notifications/{nid}``         — dismiss
  * ``GET    /api/v1/accounts/{id}/notification_settings``       — per-user
  * ``PATCH  /api/v1/accounts/{id}/notification_settings``

Auth: agent OR admin (any account member) — notifications are
per-user. Chatwoot's controller has no role guard either.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.conversations.models import Conversation
from app.domains.notifications.models import Notification
from app.domains.notifications.presenters import (
    present_notification,
    present_notification_settings,
    present_notifications_index,
)
from app.domains.notifications.schemas import NotificationSettingsUpdate
from app.domains.notifications.service import (
    count_for_user,
    destroy,
    get_or_create_settings,
    list_notifications,
    mark_all_read,
    mark_read,
    update_settings,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/notifications",
    tags=["notifications"],
)

settings_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/notification_settings",
    tags=["notifications"],
)


# ---------------------------------------------------------------------------
# Notifications list / counters
# ---------------------------------------------------------------------------
@router.get("")
async def index_notifications(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    status_filter: str | None = Query(None, alias="status"),
) -> dict[str, Any]:
    """``GET /notifications`` — paginated, ``?status=unread`` to filter."""
    assert ctx.account.id is not None and ctx.user.id is not None
    rows = await list_notifications(
        session,
        account_id=ctx.account.id,
        user_id=ctx.user.id,
        status=status_filter,
        page=page,
    )
    # Batch-load the primary actors so the presenter stays N+1-free.
    convo_ids = {
        n.primary_actor_id
        for n in rows
        if n.primary_actor_type == "Conversation"
    }
    convos: dict[tuple[str, int], Conversation] = {}
    if convo_ids:
        stmt = select(Conversation).where(
            Conversation.id.in_(convo_ids)
        )
        for c in (await session.exec(stmt)).all():
            if c.id is not None:
                convos[("Conversation", c.id)] = c
    total = await count_for_user(
        session, account_id=ctx.account.id, user_id=ctx.user.id
    )
    unread = await count_for_user(
        session,
        account_id=ctx.account.id,
        user_id=ctx.user.id,
        unread_only=True,
    )
    return present_notifications_index(
        rows,
        primary_actor_by_key=convos,
        count=total,
        unread_count=unread,
        current_page=page,
    )


@router.get("/unread_count")
async def get_unread_count(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> int:
    """``GET /notifications/unread_count`` — Rails returns a bare int."""
    assert ctx.account.id is not None and ctx.user.id is not None
    return await count_for_user(
        session,
        account_id=ctx.account.id,
        user_id=ctx.user.id,
        unread_only=True,
    )


# ---------------------------------------------------------------------------
# Mark / destroy
# ---------------------------------------------------------------------------
async def _find_notification(
    session: AsyncSession, ctx: AccountContext, notification_id: int
) -> Notification:
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.account_id == ctx.account.id,
        Notification.user_id == ctx.user.id,
    )
    row = (await session.exec(stmt)).first()
    if row is None:
        raise ChatwootHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Resource could not be found"},
        )
    return row


@router.post(
    "/{notification_id}/read", status_code=status.HTTP_200_OK
)
async def mark_notification_read(
    notification_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_notification(session, ctx, notification_id)
    row = await mark_read(session, notification=row)
    return present_notification(row)


@router.post("/read_all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /notifications/read_all`` — Chatwoot returns ``head :ok``;
    we mirror with an empty 200 body."""
    assert ctx.account.id is not None and ctx.user.id is not None
    await mark_all_read(
        session, account_id=ctx.account.id, user_id=ctx.user.id
    )
    return {}


@router.delete(
    "/{notification_id}", status_code=status.HTTP_200_OK
)
async def destroy_notification(
    notification_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_notification(session, ctx, notification_id)
    await destroy(session, notification=row)
    return {}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@settings_router.get("")
async def show_settings(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    settings = await get_or_create_settings(
        session, account_id=ctx.account.id, user_id=ctx.user.id
    )
    return present_notification_settings(settings)


@settings_router.patch("")
async def update_settings_endpoint(
    payload: NotificationSettingsUpdate,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    settings = await get_or_create_settings(
        session, account_id=ctx.account.id, user_id=ctx.user.id
    )
    settings = await update_settings(
        session,
        settings=settings,
        email=payload.selected_email_flags,
        push=payload.selected_push_flags,
    )
    return present_notification_settings(settings)


__all__ = ["router", "settings_router"]
