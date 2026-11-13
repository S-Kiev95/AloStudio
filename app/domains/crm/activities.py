"""Activities and tasks (F11): what to do, by when, with whom."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.core.logging import get_logger
from app.domains.contacts.models import Contact
from app.domains.crm.models import ACTIVITY_KINDS, CrmActivity, CrmOpportunity
from app.domains.users.models import AccountUser

log = get_logger("app.crm.activities")

STATUSES = ("pending", "overdue", "done")


def _now() -> datetime:
    return datetime.now(UTC)


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise _unprocessable("due_at is invalid") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def _check_in_account(
    session: AsyncSession, model: Any, value: Any, account_id: int, field: str
) -> None:
    if value is None:
        return
    row = await session.get(model, value) if isinstance(value, int) else None
    if row is None or getattr(row, "account_id", None) != account_id:
        raise _unprocessable(f"{field} is invalid")


async def _check_owner(session: AsyncSession, value: Any, account_id: int) -> None:
    if value is None:
        return
    member = (
        await session.exec(
            select(AccountUser.id).where(
                AccountUser.account_id == account_id, AccountUser.user_id == value
            )
        )
    ).first()
    if member is None:
        raise _unprocessable("owner_id is invalid")


async def save_activity(
    session: AsyncSession,
    *,
    account_id: int,
    activity: CrmActivity | None,
    payload: dict[str, Any],
    user_id: int | None = None,
) -> CrmActivity:
    creating = activity is None
    if creating or "title" in payload:
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise _unprocessable("Title can't be blank")
        if len(title) > 255:
            raise _unprocessable("title exceeds 255 chars")
    if creating:
        activity = CrmActivity(account_id=account_id, title="", created_by_id=user_id)
    assert activity is not None
    if "title" in payload:
        activity.title = payload["title"].strip()
    if "kind" in payload:
        if payload["kind"] not in ACTIVITY_KINDS:
            raise _unprocessable("kind is invalid")
        activity.kind = payload["kind"]
    if "description" in payload:
        activity.description = payload["description"] or None
    if "due_at" in payload:
        due = _parse_datetime(payload["due_at"])
        if due != activity.due_at:
            # A new due date gets its own reminder.
            activity.reminded_at = None
        activity.due_at = due
    for field, model in (("contact_id", Contact), ("opportunity_id", CrmOpportunity)):
        if field in payload:
            await _check_in_account(session, model, payload[field], account_id, field)
            setattr(activity, field, payload[field])
    if "owner_id" in payload:
        await _check_owner(session, payload["owner_id"], account_id)
        activity.owner_id = payload["owner_id"]
    if "done" in payload:
        activity.done_at = (activity.done_at or _now()) if payload["done"] else None
    # Opened from an opportunity: the contact comes with it.
    if activity.opportunity_id and not activity.contact_id:
        opportunity = await session.get(CrmOpportunity, activity.opportunity_id)
        if opportunity is not None:
            activity.contact_id = opportunity.contact_id
    session.add(activity)
    await session.flush()
    await session.refresh(activity)
    return activity


async def list_activities(
    session: AsyncSession,
    *,
    account_id: int,
    owner_id: int | None = None,
    contact_id: int | None = None,
    opportunity_id: int | None = None,
    status: str | None = None,
    limit: int = 300,
) -> list[CrmActivity]:
    stmt = select(CrmActivity).where(CrmActivity.account_id == account_id)
    if owner_id is not None:
        stmt = stmt.where(CrmActivity.owner_id == owner_id)
    if contact_id is not None:
        stmt = stmt.where(CrmActivity.contact_id == contact_id)
    if opportunity_id is not None:
        stmt = stmt.where(CrmActivity.opportunity_id == opportunity_id)
    if status == "done":
        stmt = stmt.where(col(CrmActivity.done_at).is_not(None)).order_by(
            col(CrmActivity.done_at).desc()
        )
    else:
        stmt = stmt.where(col(CrmActivity.done_at).is_(None))
        if status == "overdue":
            stmt = stmt.where(col(CrmActivity.due_at) < _now())
        # Soonest first; the ones without a date at the end.
        stmt = stmt.order_by(col(CrmActivity.due_at).asc().nulls_last(), col(CrmActivity.id))
    return list((await session.exec(stmt.limit(min(max(1, limit), 1000)))).all())


async def get_activity(
    session: AsyncSession, *, account_id: int, activity_id: int
) -> CrmActivity | None:
    return (
        await session.exec(
            select(CrmActivity).where(
                CrmActivity.id == activity_id, CrmActivity.account_id == account_id
            )
        )
    ).first()


async def delete_activity(session: AsyncSession, *, activity: CrmActivity) -> None:
    await session.delete(activity)
    await session.flush()


async def remind_due_activities(
    session: AsyncSession, *, now: datetime | None = None
) -> list[int]:
    """One in-app notification to the owner of each activity that just fell
    due. Returns the notification ids: the caller commits, then hands them
    to the mail and push jobs (which read the row from the database)."""
    from app.domains.notifications.models import NOTIFICATION_TYPE_CRM_ACTIVITY_DUE
    from app.domains.notifications.service import create_notification

    moment = now or _now()
    due = list(
        (
            await session.exec(
                select(CrmActivity)
                .where(
                    col(CrmActivity.due_at) <= moment,
                    col(CrmActivity.done_at).is_(None),
                    col(CrmActivity.reminded_at).is_(None),
                    col(CrmActivity.owner_id).is_not(None),
                )
                .limit(500)
            )
        ).all()
    )
    ids: list[int] = []
    for activity in due:
        assert activity.id is not None and activity.owner_id is not None
        notification = await create_notification(
            session,
            account_id=activity.account_id,
            user_id=activity.owner_id,
            notification_type=NOTIFICATION_TYPE_CRM_ACTIVITY_DUE,
            primary_actor_type="CrmActivity",
            primary_actor_id=activity.id,
            meta={"title": activity.title, "kind": activity.kind},
        )
        activity.reminded_at = moment
        session.add(activity)
        assert notification.id is not None
        ids.append(notification.id)
    await session.flush()
    if ids:
        log.info("crm.activities.reminded count=%s", len(ids))
    return ids

__all__ = [
    "STATUSES",
    "delete_activity",
    "get_activity",
    "list_activities",
    "remind_due_activities",
    "save_activity",
]
