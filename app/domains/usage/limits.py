"""Monthly spend caps (F6).

An administrator sets a cap per kind (``whatsapp``, ``ai``). This module
says how much the month has spent so far and whether the cap is reached:

  * **WhatsApp:** what Meta reported for the month (``whatsapp_cost_days``)
    plus an estimate of the billable messages we saw *after* Meta's last
    figures (their count times the average cost per category Meta reported,
    this month or the latest month it has data for). Meta reports with some
    delay, so the cap can be passed by a few messages, never by much.
  * **AI:** the sum of the estimated cost of every recorded call.

Reaching a WhatsApp cap stops template messages (campaigns, the agent, the
Bandeja's "Plantilla" button); replies inside the 24 h window still go out,
so customers aren't left unanswered. Reaching the AI cap stops the calls
to the AI provider (the agent, Instagram auto-replies, Help Center search
falls back to plain text search). The worker tells the admins at 80 % and
100 %, once per month and level.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.billing.service import plan_usage_cap
from app.domains.usage.models import (
    KIND_AI,
    KIND_WHATSAPP,
    UsageLimit,
    UsageRecord,
    WhatsappCostDay,
)

log = logging.getLogger(__name__)

KINDS = (KIND_WHATSAPP, KIND_AI)
ALERT_LEVELS = (80, 100)


def _month_start(now: datetime | None = None) -> tuple[date, datetime]:
    now = now or datetime.now(UTC)
    first = now.date().replace(day=1)
    return first, datetime(first.year, first.month, 1, tzinfo=UTC)


async def _unit_costs(session: AsyncSession, account_id: int) -> dict[str, Decimal]:
    """Average cost of a billable message per category, from the latest
    month Meta reported data for."""
    rows = (
        await session.exec(
            select(
                WhatsappCostDay.pricing_category,
                func.sum(WhatsappCostDay.volume),
                func.sum(WhatsappCostDay.cost),
            )
            .where(
                WhatsappCostDay.account_id == account_id,
                WhatsappCostDay.pricing_type == "REGULAR",
                WhatsappCostDay.volume > 0,
            )
            .group_by(WhatsappCostDay.pricing_category)
        )
    ).all()
    return {cat: Decimal(cost) / int(vol) for cat, vol, cost in rows if vol}


async def whatsapp_month_spend(
    session: AsyncSession, account_id: int, now: datetime | None = None
) -> Decimal:
    first, start = _month_start(now)
    reported, last_day = (
        await session.exec(
            select(func.sum(WhatsappCostDay.cost), func.max(WhatsappCostDay.day)).where(
                WhatsappCostDay.account_id == account_id,
                WhatsappCostDay.day >= first,
            )
        )
    ).one()
    # Billable messages Meta hasn't reported yet: those after its last day.
    since = start
    if last_day is not None:
        nxt = last_day.toordinal() + 1
        d = date.fromordinal(nxt)
        since = datetime(d.year, d.month, d.day, tzinfo=UTC)
    pending = (
        await session.exec(
            select(UsageRecord.category, func.count(), func.sum(UsageRecord.cost))
            .where(
                UsageRecord.account_id == account_id,
                UsageRecord.kind == KIND_WHATSAPP,
                UsageRecord.billable.is_(True),  # type: ignore[union-attr]
                UsageRecord.occurred_at >= since,
            )
            .group_by(UsageRecord.category)
        )
    ).all()
    estimate = Decimal(0)
    units: dict[str, Decimal] | None = None
    for category, count, exact in pending:
        if exact is not None:
            estimate += Decimal(exact)
            continue
        if units is None:
            units = await _unit_costs(session, account_id)
        estimate += units.get(str(category or "").upper(), Decimal(0)) * count
    return Decimal(reported or 0) + estimate


async def ai_month_spend(
    session: AsyncSession, account_id: int, now: datetime | None = None
) -> Decimal:
    _, start = _month_start(now)
    total = (
        await session.exec(
            select(func.sum(UsageRecord.cost)).where(
                UsageRecord.account_id == account_id,
                UsageRecord.kind == KIND_AI,
                UsageRecord.occurred_at >= start,
            )
        )
    ).one()
    return Decimal(total or 0)


async def month_spend(session: AsyncSession, account_id: int, kind: str) -> Decimal:
    if kind == KIND_WHATSAPP:
        return await whatsapp_month_spend(session, account_id)
    return await ai_month_spend(session, account_id)


async def get_limit(session: AsyncSession, account_id: int, kind: str) -> UsageLimit | None:
    return (
        await session.exec(
            select(UsageLimit).where(UsageLimit.account_id == account_id, UsageLimit.kind == kind)
        )
    ).first()


async def plan_month_spend(session: AsyncSession, account_id: int) -> Decimal:
    """WhatsApp + AI this month, in USD, for the plan's cap (F2). WhatsApp
    counts only while Meta bills the account in USD: its figures come in the
    WhatsApp Business Account's currency, and there is no rate to convert."""
    first, _ = _month_start()
    currencies = set(
        (
            await session.exec(
                select(WhatsappCostDay.currency)
                .where(WhatsappCostDay.account_id == account_id, WhatsappCostDay.day >= first)
                .distinct()
            )
        ).all()
    )
    spend = await ai_month_spend(session, account_id)
    if currencies <= {None, "USD"}:
        spend += await whatsapp_month_spend(session, account_id)
    else:
        log.warning(
            "usage.limits.plan_cap_whatsapp_skipped account_id=%s currencies=%s",
            account_id,
            sorted(c for c in currencies if c),
        )
    return spend


async def limit_reached(session: AsyncSession, account_id: int, kind: str) -> bool:
    """Whether this month's spend reached the admin's cap for ``kind`` or,
    on a multitenant install, the plan's cap on WhatsApp + AI together
    (False without either). Never raises: a broken check must not stop the
    account's messages."""
    try:
        cap = await get_limit(session, account_id, kind)
        if cap is not None and await month_spend(session, account_id, kind) >= cap.monthly_limit:
            return True
        plan_cap = await plan_usage_cap(session, account_id)
        return plan_cap is not None and await plan_month_spend(session, account_id) >= plan_cap
    except Exception:
        log.exception("usage.limits.check_failed account_id=%s kind=%s", account_id, kind)
        return False


async def limits_status(session: AsyncSession, account_id: int) -> list[dict[str, Any]]:
    out = []
    for kind in KINDS:
        cap = await get_limit(session, account_id, kind)
        spent = await month_spend(session, account_id, kind)
        limit = cap.monthly_limit if cap else None
        out.append(
            {
                "kind": kind,
                "monthly_limit": float(limit) if limit is not None else None,
                "spent": round(float(spent), 4),
                "percent": round(float(spent / limit * 100), 1) if limit else None,
                "reached": bool(limit is not None and spent >= limit),
            }
        )
    return out


async def set_limit(
    session: AsyncSession, account_id: int, kind: str, monthly_limit: float | None
) -> None:
    """Set, change (from the next check on) or remove (``None``) a cap."""
    cap = await get_limit(session, account_id, kind)
    if monthly_limit is None:
        if cap is not None:
            await session.delete(cap)
        await session.flush()
        return
    if cap is None:
        cap = UsageLimit(account_id=account_id, kind=kind, monthly_limit=Decimal(0))
    cap.monthly_limit = Decimal(str(monthly_limit)).quantize(Decimal("0.01"))
    # A new cap gets its alerts again this month.
    cap.notified_month = None
    cap.notified_level = 0
    session.add(cap)
    await session.flush()


async def notify_limits(session: AsyncSession) -> list[int]:
    """Worker: tell each account's admins when a cap crosses 80 % or 100 %
    this month (once per level). Returns the notification ids; the caller
    commits and hands them to the mail and push jobs."""
    from app.domains.notifications.models import NOTIFICATION_TYPE_USAGE_LIMIT
    from app.domains.notifications.service import create_notification
    from app.domains.users.models import ACCOUNT_USER_ROLE_ADMINISTRATOR, AccountUser

    month = datetime.now(UTC).strftime("%Y-%m")
    ids: list[int] = []
    for cap in (await session.exec(select(UsageLimit))).all():
        if cap.monthly_limit <= 0:
            continue
        spent = await month_spend(session, cap.account_id, cap.kind)
        percent = spent / cap.monthly_limit * 100
        level = max((lvl for lvl in ALERT_LEVELS if percent >= lvl), default=0)
        already = cap.notified_level if cap.notified_month == month else 0
        if level <= already:
            continue
        label = "WhatsApp" if cap.kind == KIND_WHATSAPP else "IA / AI"
        title = f"{label}: {level}% ({spent:.2f} / {cap.monthly_limit:.2f})"
        admins = (
            await session.exec(
                select(AccountUser.user_id).where(
                    AccountUser.account_id == cap.account_id,
                    AccountUser.role == ACCOUNT_USER_ROLE_ADMINISTRATOR,
                )
            )
        ).all()
        for user_id in admins:
            notification = await create_notification(
                session,
                account_id=cap.account_id,
                user_id=user_id,
                notification_type=NOTIFICATION_TYPE_USAGE_LIMIT,
                primary_actor_type="UsageLimit",
                primary_actor_id=cap.id,  # type: ignore[arg-type]
                meta={"title": title, "kind": cap.kind, "level": level},
            )
            assert notification.id is not None
            ids.append(notification.id)
        cap.notified_month = month
        cap.notified_level = level
        session.add(cap)
    await session.flush()
    return ids


__all__ = [
    "KINDS",
    "ai_month_spend",
    "limit_reached",
    "limits_status",
    "notify_limits",
    "set_limit",
    "whatsapp_month_spend",
]
