"""Notification service: list / count / mark / destroy + setting upsert.

The listener (``listener.py``) creates rows; this module exposes the
read/update side the HTTP router and tests consume.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func as sa_func
from sqlmodel import select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.notifications.models import (
    Notification,
    NotificationSetting,
)


RESULTS_PER_PAGE = 15


# ---------------------------------------------------------------------------
# List / count
# ---------------------------------------------------------------------------
async def list_notifications(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int,
    status: str | None,
    page: int,
) -> list[Notification]:
    """``GET /notifications`` rows for the calling user.

    ``status="unread"`` filters to unread only; anything else returns
    the full set (read + unread, no snooze filter — the popover renders
    everything).
    """
    stmt = select(Notification).where(
        Notification.account_id == account_id,
        Notification.user_id == user_id,
    )
    if status == "unread":
        stmt = stmt.where(Notification.read_at.is_(None))  # type: ignore[union-attr]
    offset = (max(page, 1) - 1) * RESULTS_PER_PAGE
    stmt = (
        stmt.order_by(Notification.id.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(RESULTS_PER_PAGE)
    )
    return list((await session.exec(stmt)).all())


async def count_for_user(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int,
    unread_only: bool = False,
) -> int:
    stmt = select(sa_func.count(Notification.id)).where(  # type: ignore[arg-type]
        Notification.account_id == account_id,
        Notification.user_id == user_id,
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))  # type: ignore[union-attr]
    return int((await session.exec(stmt)).one() or 0)  # type: ignore[call-overload]


# ---------------------------------------------------------------------------
# Mark read / unread / destroy
# ---------------------------------------------------------------------------
async def mark_read(
    session: AsyncSession, *, notification: Notification
) -> Notification:
    notification.read_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(notification)
    await session.flush()
    return notification


async def mark_unread(
    session: AsyncSession, *, notification: Notification
) -> Notification:
    notification.read_at = None
    session.add(notification)
    await session.flush()
    return notification


async def mark_all_read(
    session: AsyncSession, *, account_id: int, user_id: int
) -> int:
    """Set ``read_at = now()`` on every unread notification for the
    (account, user). Returns the affected row count."""
    now = datetime.now(UTC).replace(tzinfo=None)
    stmt = (
        update(Notification)
        .where(
            Notification.account_id == account_id,
            Notification.user_id == user_id,
            Notification.read_at.is_(None),  # type: ignore[union-attr]
        )
        .values(read_at=now)
    )
    result = await session.exec(stmt)  # type: ignore[call-arg]
    await session.flush()
    return result.rowcount or 0  # type: ignore[union-attr]


async def destroy(
    session: AsyncSession, *, notification: Notification
) -> None:
    await session.delete(notification)
    await session.flush()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
async def get_or_create_settings(
    session: AsyncSession, *, account_id: int, user_id: int
) -> NotificationSetting:
    """One row per (account, user). Lazily created on first read."""
    stmt = select(NotificationSetting).where(
        NotificationSetting.account_id == account_id,
        NotificationSetting.user_id == user_id,
    )
    row = (await session.exec(stmt)).first()
    if row is not None:
        return row
    # Default: every notification type subscribed on both channels.
    # Chatwoot upstream defaults to fully-on; we keep that.
    from app.domains.notifications.models import (
        _NOTIFICATION_TYPE_STR_TO_INT,
    )

    every_type = list(_NOTIFICATION_TYPE_STR_TO_INT.keys())
    row = NotificationSetting(
        account_id=account_id,
        user_id=user_id,
        email_subscriptions=every_type,
        push_subscriptions=every_type,
    )
    session.add(row)
    await session.flush()
    return row


async def update_settings(
    session: AsyncSession,
    *,
    settings: NotificationSetting,
    email: list[str] | None,
    push: list[str] | None,
) -> NotificationSetting:
    if email is not None:
        settings.email_subscriptions = email
    if push is not None:
        settings.push_subscriptions = push
    session.add(settings)
    await session.flush()
    return settings


# ---------------------------------------------------------------------------
# Listener helpers (called from listener.py)
# ---------------------------------------------------------------------------
async def create_notification(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int,
    notification_type: int,
    primary_actor_type: str,
    primary_actor_id: int,
    secondary_actor_type: str | None = None,
    secondary_actor_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> Notification:
    """Insert one row. Caller is responsible for the no-loop checks
    (don't notify the user that performed the action)."""
    now = datetime.now(UTC).replace(tzinfo=None)
    row = Notification(
        account_id=account_id,
        user_id=user_id,
        notification_type=notification_type,
        primary_actor_type=primary_actor_type,
        primary_actor_id=primary_actor_id,
        secondary_actor_type=secondary_actor_type,
        secondary_actor_id=secondary_actor_id,
        last_activity_at=now,
        meta=meta or {},
    )
    session.add(row)
    await session.flush()
    return row


__all__ = [
    "RESULTS_PER_PAGE",
    "count_for_user",
    "create_notification",
    "destroy",
    "get_or_create_settings",
    "list_notifications",
    "mark_all_read",
    "mark_read",
    "mark_unread",
    "update_settings",
]
