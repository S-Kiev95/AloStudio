"""Monthly spend caps (F6).

An administrator sets a cap per kind (``whatsapp``, ``ai``). This module
says how much the month has spent so far and whether the cap is reached:

  * **WhatsApp:** what Meta reported for the month (``whatsapp_cost_days``)
    plus an estimate of the billable messages we saw *after* Meta's last
    figures (their count times the average cost per category Meta reported,
    this month or the latest month it has data for). Meta reports with some
    delay, so the cap can be passed by a few messages, never by much.
  * **AI:** the sum of the estimated cost of every recorded call.

On a multitenant install (F2) the plan adds an AI cap that AI credit
extends (:func:`credit_balance`); WhatsApp is the client's own bill with
Meta, so only the admin's cap stops it.

Reaching a WhatsApp cap stops template messages (campaigns, the agent, the
Bandeja's "Plantilla" button); replies inside the 24 h window still go out,
so customers aren't left unanswered. Reaching the AI cap stops the calls
to the AI provider (the agent, Instagram auto-replies, Help Center search
falls back to plain text search). The worker tells the admins at 80 % and
100 %, once per month and level, of an admin's cap and of the plan's.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.billing.models import ACTIVE_STATUSES, AccountSubscription, CreditMonthUsage
from app.domains.billing.service import credit_left_of, credit_purchases, plan_usage_cap
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


def _excess(total: Decimal, before: Decimal, cap: Decimal | None) -> Decimal:
    """Credit a month uses: its AI spend above the cap, less what was
    already above it before the first purchase (the AI was stopped then;
    credit pays only for what came after)."""
    if cap is None:
        return Decimal(0)
    return max(total - cap, Decimal(0)) - max(before - cap, Decimal(0))


async def _ai_spend_by_month(
    session: AsyncSession, account_id: int, since: datetime, until: datetime | None = None
) -> dict[date, Decimal]:
    # Months in UTC whatever the session's time zone, like _month_start.
    month = func.date_trunc("month", func.timezone("UTC", UsageRecord.occurred_at))
    query = select(month, func.sum(UsageRecord.cost)).where(
        UsageRecord.account_id == account_id,
        UsageRecord.kind == KIND_AI,
        UsageRecord.occurred_at >= since,
    )
    if until is not None:
        query = query.where(UsageRecord.occurred_at < until)
    rows = (await session.exec(query.group_by(month))).all()
    return {m.date(): Decimal(spent or 0) for m, spent in rows}


async def credit_balance(
    session: AsyncSession, account_id: int, *, cap: Decimal | None = None, cap_known: bool = False
) -> Decimal:
    """AI credit left (F2): bought, less refunds, less every month's AI
    spend above the plan's cap since the first purchase. Computed, never
    deducted per call; 0 without purchases, never negative.

    Closed months are frozen in ``credit_month_usages`` the first time they
    are needed (with the cap of that moment), so a later change of plan
    doesn't rewrite them and only the current month is read live."""
    purchases = await credit_purchases(session, account_id)
    if not purchases:
        return Decimal(0)
    bought = sum((credit_left_of(p) for p in purchases), Decimal(0))
    if not cap_known:
        cap = await plan_usage_cap(session, account_id)
    first_paid = min(p.paid_at for p in purchases)
    first_month = first_paid.astimezone(UTC).date().replace(day=1)
    this_month, _ = _month_start()
    first_start = datetime(first_month.year, first_month.month, 1, tzinfo=UTC)
    before = (await _ai_spend_by_month(session, account_id, first_start, first_paid)).get(
        first_month, Decimal(0)
    )
    frozen = {
        row.month: row.used
        for row in (
            await session.exec(
                select(CreditMonthUsage).where(
                    CreditMonthUsage.account_id == account_id,
                    CreditMonthUsage.month >= first_month,
                )
            )
        ).all()
    }
    since = first_start
    if frozen:
        nxt = (max(frozen).replace(day=28) + timedelta(days=4)).replace(day=1)
        since = datetime(nxt.year, nxt.month, 1, tzinfo=UTC)
    used = sum(frozen.values(), Decimal(0))
    for month, total in (await _ai_spend_by_month(session, account_id, since)).items():
        excess = _excess(total, before if month == first_month else Decimal(0), cap)
        used += excess
        if month < this_month:
            try:
                async with session.begin_nested():
                    session.add(CreditMonthUsage(account_id=account_id, month=month, used=excess))
            except IntegrityError:
                pass  # another request froze it first
    return max(bought - used, Decimal(0))


async def limit_reached(session: AsyncSession, account_id: int, kind: str) -> bool:
    """Whether this month's spend reached the admin's cap for ``kind`` or,
    on a multitenant install, the plan's AI cap with no credit left (False
    without either). WhatsApp is the client's own bill with Meta, so only
    the admin's cap stops it. Never raises: a broken check must not stop
    the account's messages."""
    try:
        cap = await get_limit(session, account_id, kind)
        if cap is not None and await month_spend(session, account_id, kind) >= cap.monthly_limit:
            return True
        if kind != KIND_AI:
            return False
        plan_cap = await plan_usage_cap(session, account_id)
        if plan_cap is None or await ai_month_spend(session, account_id) < plan_cap:
            return False
        return await credit_balance(session, account_id, cap=plan_cap, cap_known=True) <= 0
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
        for user_id in await _admin_ids(session, cap.account_id):
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
    ids += await _notify_plan_alerts(session, month)
    await session.flush()
    return ids


async def _admin_ids(session: AsyncSession, account_id: int) -> list[int]:
    from app.domains.users.models import ACCOUNT_USER_ROLE_ADMINISTRATOR, AccountUser

    rows = (
        await session.exec(
            select(AccountUser.user_id).where(
                AccountUser.account_id == account_id,
                AccountUser.role == ACCOUNT_USER_ROLE_ADMINISTRATOR,
            )
        )
    ).all()
    return [user_id for user_id in rows if user_id is not None]


# AI credit is "low" at this share of the latest purchase's credit or less.
CREDIT_LOW_SHARE = Decimal("0.2")
# A day is "unusual" at this many times the daily average of the previous
# ``SPIKE_DAYS`` days, and at least ``SPIKE_MIN_USD`` (a few cents of AI
# are never news).
SPIKE_FACTOR = 3
SPIKE_DAYS = 14
SPIKE_MIN_USD = Decimal("1")


async def _tell_admins(
    session: AsyncSession, sub: AccountSubscription, *, title: str, source: str, level: int
) -> list[int]:
    from app.domains.notifications.models import NOTIFICATION_TYPE_USAGE_LIMIT
    from app.domains.notifications.service import create_notification

    ids: list[int] = []
    for user_id in await _admin_ids(session, sub.account_id):
        notification = await create_notification(
            session,
            account_id=sub.account_id,
            user_id=user_id,
            notification_type=NOTIFICATION_TYPE_USAGE_LIMIT,
            primary_actor_type="AccountSubscription",
            primary_actor_id=sub.id,  # type: ignore[arg-type]
            meta={"title": title, "kind": KIND_AI, "level": level, "source": source},
        )
        assert notification.id is not None
        ids.append(notification.id)
    return ids


async def _ai_spend_by_day(
    session: AsyncSession, account_id: int, since: datetime
) -> dict[date, Decimal]:
    day = func.date_trunc("day", UsageRecord.occurred_at)
    rows = (
        await session.exec(
            select(day, func.coalesce(func.sum(UsageRecord.cost), 0))  # type: ignore[call-overload]
            .where(
                UsageRecord.account_id == account_id,
                UsageRecord.kind == KIND_AI,
                UsageRecord.occurred_at >= since,
            )
            .group_by(day)
        )
    ).all()
    return {d.date(): Decimal(total) for d, total in rows}


async def _notify_plan_alerts(session: AsyncSession, month: str) -> list[int]:
    """F2 multitenant, for each account with a plan, once per level:

    * the plan's AI cap at 80 % / 100 % of the month (at 100 % the AI goes
      on with AI credit if there is some), ``source: plan``;
    * the AI credit low (under 20 % of the latest purchase) and used up,
      once per purchase, ``source: credit``;
    * a day of AI spend far above the account's usual, once a day,
      ``source: spike``.

    The mail of each says what it means (``notif.lead.usage_limit_<source>``)."""
    if not get_settings().multitenant:
        return []
    ids: list[int] = []
    subs = (
        await session.exec(
            select(AccountSubscription).where(AccountSubscription.status.in_(ACTIVE_STATUSES))  # type: ignore[attr-defined]
        )
    ).all()
    now = datetime.now(UTC)
    today = now.date()
    for sub in subs:
        account_id = sub.account_id
        cap = await plan_usage_cap(session, account_id)
        if cap is not None:
            spent = await ai_month_spend(session, account_id)
            percent = spent / cap * 100
            level = max((lvl for lvl in ALERT_LEVELS if percent >= lvl), default=0)
            already = sub.cap_notified_level if sub.cap_notified_month == month else 0
            if level > already:
                title = f"IA / AI ({sub.plan_name or 'plan'}): {level}% ({spent:.2f} / {cap:.2f})"
                ids += await _tell_admins(session, sub, title=title, source="plan", level=level)
                sub.cap_notified_month = month
                sub.cap_notified_level = level

        purchases = await credit_purchases(session, account_id)
        if purchases:
            latest = purchases[0]
            balance = await credit_balance(session, account_id, cap=cap, cap_known=True)
            low = credit_left_of(latest) * CREDIT_LOW_SHARE
            level = 100 if balance <= 0 else 20 if balance <= low else 0
            already = (
                sub.credit_notified_level if sub.credit_notified_purchase_id == latest.id else 0
            )
            if level > already:
                title = f"Créditos de IA / AI credit: {balance:.2f} USD"
                ids += await _tell_admins(session, sub, title=title, source="credit", level=level)
                sub.credit_notified_purchase_id = latest.id
                sub.credit_notified_level = level

        if sub.spike_notified_on != today:
            first = datetime(today.year, today.month, today.day, tzinfo=UTC) - timedelta(
                days=SPIKE_DAYS
            )
            by_day = await _ai_spend_by_day(session, account_id, first)
            today_spent = by_day.pop(today, Decimal(0))
            average = sum(by_day.values(), Decimal(0)) / SPIKE_DAYS
            # A new account has no usual yet: nothing to compare with.
            if average > 0 and today_spent >= max(SPIKE_MIN_USD, average * SPIKE_FACTOR):
                title = f"IA / AI: {today_spent:.2f} USD (≈ {average:.2f} / día-day)"
                ids += await _tell_admins(session, sub, title=title, source="spike", level=0)
                sub.spike_notified_on = today
        session.add(sub)
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
