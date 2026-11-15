"""The month's spend for one account (F6): what Meta charged for WhatsApp,
how it splits by number, category, country and campaign, and the AI calls."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.campaigns.models import Campaign
from app.domains.inboxes.models import Inbox
from app.domains.usage.ai import PRICES_CHECKED_ON
from app.domains.usage.models import KIND_AI, KIND_WHATSAPP, UsageRecord, WhatsappCostDay


def month_bounds(month: str | None) -> tuple[date, date, datetime, datetime]:
    """``YYYY-MM`` → first and last day, and the UTC datetimes around them.
    Defaults to the current month; 422 on anything else."""
    today = datetime.now(UTC).date()
    if month:
        try:
            year, mon = (int(x) for x in month.split("-", 1))
            first = date(year, mon, 1)
        except (ValueError, TypeError) as exc:
            raise ChatwootHTTPException(
                status_code=422, detail={"message": "month va como AAAA-MM."}
            ) from exc
    else:
        first = today.replace(day=1)
    nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    last = date.fromordinal(nxt.toordinal() - 1)
    return (
        first,
        last,
        datetime(first.year, first.month, 1, tzinfo=UTC),
        datetime(nxt.year, nxt.month, 1, tzinfo=UTC),
    )


def _money(value: Decimal | float | None) -> float:
    return round(float(value or 0), 4)


async def _whatsapp_meta(
    session: AsyncSession, account_id: int, first: date, last: date
) -> dict[str, Any]:
    rows = (
        await session.exec(
            select(WhatsappCostDay).where(
                WhatsappCostDay.account_id == account_id,
                WhatsappCostDay.day >= first,
                WhatsappCostDay.day <= last,
            )
        )
    ).all()
    inbox_names = {
        i.id: i.name
        for i in (await session.exec(select(Inbox).where(Inbox.account_id == account_id))).all()
    }
    by_category: dict[str, list[Any]] = defaultdict(lambda: [0, Decimal(0)])
    by_inbox: dict[int, list[Any]] = defaultdict(lambda: [0, Decimal(0)])
    by_country: dict[str, list[Any]] = defaultdict(lambda: [0, Decimal(0)])
    by_day: dict[date, Decimal] = defaultdict(Decimal)
    regular: dict[str, list[Any]] = defaultdict(lambda: [0, Decimal(0)])
    currencies: set[str] = set()
    total = Decimal(0)
    volume = 0
    billable = 0
    synced: datetime | None = None
    for r in rows:
        for bucket, key in (
            (by_category, r.pricing_category),
            (by_inbox, r.inbox_id),
            (by_country, r.country),
        ):
            bucket[key][0] += r.volume
            bucket[key][1] += r.cost
        by_day[r.day] += r.cost
        total += r.cost
        volume += r.volume
        if r.pricing_type == "REGULAR":
            billable += r.volume
            regular[r.pricing_category][0] += r.volume
            regular[r.pricing_category][1] += r.cost
        if r.currency:
            currencies.add(r.currency)
        synced = max(synced, r.synced_at) if synced else r.synced_at

    def listing(bucket: dict[Any, list[Any]], name: str) -> list[dict[str, Any]]:
        return sorted(
            (
                {name: k, "volume": v[0], "cost": _money(v[1])}
                for k, v in bucket.items()
            ),
            key=lambda x: (-x["cost"], -x["volume"]),
        )

    return {
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "total_cost": _money(total),
        "messages": volume,
        "billable_messages": billable,
        "by_category": listing(by_category, "category"),
        "by_country": listing(by_country, "country"),
        "by_inbox": [
            {**row, "name": inbox_names.get(row["inbox_id"])}
            for row in listing(by_inbox, "inbox_id")
        ],
        "by_day": [
            {"day": d.isoformat(), "cost": _money(c)} for d, c in sorted(by_day.items())
        ],
        "last_synced_at": int(synced.timestamp()) if synced else None,
        # Unit cost per category (billable only), to value per-campaign counts.
        "_unit_cost": {
            k: (v[1] / v[0]) for k, v in regular.items() if v[0]
        },
    }


async def _campaigns(
    session: AsyncSession,
    account_id: int,
    start: datetime,
    end: datetime,
    unit_cost: dict[str, Decimal],
) -> list[dict[str, Any]]:
    rows = (
        await session.exec(
            select(
                UsageRecord.campaign_id,
                UsageRecord.category,
                UsageRecord.billable,
                func.count(),
                func.sum(UsageRecord.cost),
            )
            .where(
                UsageRecord.account_id == account_id,
                UsageRecord.kind == KIND_WHATSAPP,
                UsageRecord.campaign_id.is_not(None),  # type: ignore[union-attr]
                UsageRecord.occurred_at >= start,
                UsageRecord.occurred_at < end,
            )
            .group_by(UsageRecord.campaign_id, UsageRecord.category, UsageRecord.billable)
        )
    ).all()
    if not rows:
        return []
    per: dict[int, dict[str, Any]] = {}
    for campaign_id, category, is_billable, count, reported in rows:
        entry = per.setdefault(
            campaign_id,
            {"messages": 0, "billable_messages": 0, "estimated_cost": Decimal(0), "exact": True},
        )
        entry["messages"] += count
        if is_billable:
            entry["billable_messages"] += count
            if reported is not None:
                entry["estimated_cost"] += reported
            else:
                unit = unit_cost.get(str(category or "").upper())
                if unit is None:
                    entry["exact"] = False
                else:
                    entry["estimated_cost"] += unit * count
    campaigns = {
        c.id: c
        for c in (
            await session.exec(
                select(Campaign).where(
                    Campaign.account_id == account_id,
                    Campaign.id.in_(list(per)),  # type: ignore[union-attr]
                )
            )
        ).all()
    }
    out = []
    for campaign_id, entry in per.items():
        c = campaigns.get(campaign_id)
        out.append(
            {
                "campaign_id": c.display_id if c else None,
                "title": c.title if c else None,
                "inbox_id": c.inbox_id if c else None,
                "messages": entry["messages"],
                "billable_messages": entry["billable_messages"],
                "estimated_cost": _money(entry["estimated_cost"]),
                "complete": entry["exact"],
            }
        )
    return sorted(out, key=lambda x: -x["estimated_cost"])


async def _ai(
    session: AsyncSession, account_id: int, start: datetime, end: datetime
) -> dict[str, Any]:
    rows = (
        await session.exec(
            select(
                UsageRecord.category,
                UsageRecord.model,
                func.count(),
                func.sum(UsageRecord.input_tokens),
                func.sum(UsageRecord.output_tokens),
                func.sum(UsageRecord.cost),
            )
            .where(
                UsageRecord.account_id == account_id,
                UsageRecord.kind == KIND_AI,
                UsageRecord.occurred_at >= start,
                UsageRecord.occurred_at < end,
            )
            .group_by(UsageRecord.category, UsageRecord.model)
        )
    ).all()
    items = [
        {
            "purpose": purpose,
            "model": model,
            "requests": int(count),
            "input_tokens": int(tin or 0),
            "output_tokens": int(tout or 0),
            "cost": _money(cost),
        }
        for purpose, model, count, tin, tout, cost in rows
    ]
    items.sort(key=lambda x: -x["cost"])
    return {
        "currency": "USD",
        "total_cost": _money(sum((Decimal(str(i["cost"])) for i in items), Decimal(0))),
        "requests": sum(i["requests"] for i in items),
        "items": items,
        "prices_checked_on": PRICES_CHECKED_ON,
    }


async def month_summary(
    session: AsyncSession, *, account_id: int, month: str | None
) -> dict[str, Any]:
    first, last, start, end = month_bounds(month)
    whatsapp = await _whatsapp_meta(session, account_id, first, last)
    unit_cost = whatsapp.pop("_unit_cost")
    return {
        "month": first.strftime("%Y-%m"),
        "whatsapp": whatsapp,
        "campaigns": await _campaigns(session, account_id, start, end, unit_cost),
        "ai": await _ai(session, account_id, start, end),
    }


__all__ = ["month_bounds", "month_summary"]
