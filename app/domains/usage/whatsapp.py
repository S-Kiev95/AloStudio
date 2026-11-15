"""WhatsApp spend (F6).

Two sources, on purpose:

  * **Per message** — Meta's status webhook carries a ``pricing`` object
    (``billable``, ``category``, ``type``) on sent/delivered statuses. We keep
    one :class:`UsageRecord` per WAMID, with the inbox and the campaign the
    message belongs to. That is what lets us split spend by campaign.
  * **What Meta charges** — ``pricing_analytics`` on the WhatsApp Business
    Account gives volume and approximate cost per day, category, pricing
    type and country, in the account's currency. Synced into
    :class:`WhatsappCostDay` (daily by the worker, on demand from the panel).
    The rate card is a downloadable PDF/CSV that changes every quarter, so
    taking Meta's own figure beats keeping a price table here.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Message
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD, Inbox, WhatsappChannel
from app.domains.usage.models import KIND_WHATSAPP, UsageRecord, WhatsappCostDay

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per message, from the status webhook
# ---------------------------------------------------------------------------
async def record_message_pricing(
    session: AsyncSession, *, message: Message, status: dict[str, Any]
) -> None:
    """Keep the ``pricing`` Meta sent for one of our messages. Idempotent per
    WAMID (later statuses refresh the row). Never raises: it runs inside the
    webhook."""
    pricing = status.get("pricing")
    if not isinstance(pricing, dict) or not message.source_id:
        return
    try:
        attrs = message.additional_attributes or {}
        campaign_id = attrs.get("campaign_id") if isinstance(attrs, dict) else None
        ts = status.get("timestamp")
        occurred = (
            datetime.fromtimestamp(int(ts), tz=UTC) if str(ts or "").isdigit() else datetime.now(UTC)
        )
        cost = pricing.get("cost") if isinstance(pricing.get("cost"), dict) else {}
        values = {
            "account_id": message.account_id,
            "kind": KIND_WHATSAPP,
            "occurred_at": occurred,
            "inbox_id": message.inbox_id,
            "campaign_id": int(campaign_id) if str(campaign_id or "").isdigit() else None,
            "category": str(pricing.get("category") or "") or None,
            "pricing_type": str(pricing.get("type") or "") or None,
            "billable": bool(pricing.get("billable")),
            "model": str(pricing.get("pricing_model") or "") or None,
            "cost": Decimal(str(cost["amount"])) if cost.get("amount") is not None else None,
            "currency": cost.get("currency"),
            "source_id": message.source_id,
        }
        stmt = insert(UsageRecord.__table__).values(  # type: ignore[attr-defined]
            **values, created_at=datetime.now(UTC), updated_at=datetime.now(UTC)
        )
        refresh = {k: stmt.excluded[k] for k in ("category", "pricing_type", "billable", "model")}
        refresh["updated_at"] = stmt.excluded.updated_at
        if values["cost"] is not None:
            refresh["cost"] = stmt.excluded.cost
            refresh["currency"] = stmt.excluded.currency
        async with session.begin_nested():
            await session.execute(
                stmt.on_conflict_do_update(
                    constraint="uniq_usage_records_source", set_=refresh
                )
            )
    except Exception:
        log.exception("usage.whatsapp.pricing_failed wamid=%s", message.source_id)


# ---------------------------------------------------------------------------
# What Meta charges, from pricing_analytics
# ---------------------------------------------------------------------------
def _analytics_field(phone_digits: str, start: int, end: int) -> str:
    dims = json.dumps(["PRICING_CATEGORY", "PRICING_TYPE", "COUNTRY"])
    phones = json.dumps([phone_digits]) if phone_digits else None
    parts = [
        f"pricing_analytics.start({start}).end({end}).granularity(DAILY)",
        f".dimensions({dims})",
    ]
    if phones:
        parts.insert(1, f".phone_numbers({phones})")
    return "".join(parts)


async def sync_costs(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    since: date,
    until: date,
) -> int:
    """Pull ``pricing_analytics`` for this number between ``since`` and
    ``until`` (inclusive) and upsert one row per day / category / type /
    country. Returns the number of rows written. Raises the Graph error
    (422 with Meta's message) so the panel can show it."""
    from app.domains.whatsapp.templates import _graph_call, _waba

    waba, _ = _waba(channel)
    start = int(datetime(since.year, since.month, since.day, tzinfo=UTC).timestamp())
    end_day = until + timedelta(days=1)
    end = int(datetime(end_day.year, end_day.month, end_day.day, tzinfo=UTC).timestamp())
    phone = "".join(c for c in (channel.phone_number or "") if c.isdigit())
    body = await _graph_call(
        channel,
        "GET",
        waba,
        params={"fields": f"currency,{_analytics_field(phone, start, end)}"},
    )
    currency = body.get("currency")
    analytics = body.get("pricing_analytics") or {}
    blocks = analytics.get("data") if isinstance(analytics, dict) else None
    now = datetime.now(UTC)
    written = 0
    for block in blocks or []:
        for point in (block or {}).get("data_points") or []:
            if not isinstance(point, dict) or point.get("start") is None:
                continue
            day = datetime.fromtimestamp(int(point["start"]), tz=UTC).date()
            values = {
                "account_id": channel.account_id,
                "inbox_id": inbox.id,
                "day": day,
                "pricing_category": str(point.get("pricing_category") or "UNKNOWN"),
                "pricing_type": str(point.get("pricing_type") or "UNKNOWN"),
                "country": str(point.get("country") or "??"),
                "volume": int(point.get("volume") or 0),
                "cost": Decimal(str(point.get("cost") or 0)),
                "currency": currency,
                "synced_at": now,
            }
            stmt = insert(WhatsappCostDay.__table__).values(**values)  # type: ignore[attr-defined]
            await session.execute(
                stmt.on_conflict_do_update(
                    constraint="uniq_whatsapp_cost_days_bucket",
                    set_={
                        "volume": stmt.excluded.volume,
                        "cost": stmt.excluded.cost,
                        "currency": stmt.excluded.currency,
                        "synced_at": stmt.excluded.synced_at,
                    },
                )
            )
            written += 1
    await session.flush()
    return written


async def cloud_numbers(
    session: AsyncSession, account_id: int | None = None
) -> list[tuple[WhatsappChannel, Inbox]]:
    """Every WhatsApp Cloud number (optionally of one account) with its inbox."""
    stmt = select(WhatsappChannel, Inbox).where(
        WhatsappChannel.provider == WHATSAPP_PROVIDER_CLOUD,
        Inbox.channel_id == WhatsappChannel.id,
        Inbox.channel_type == "Channel::Whatsapp",
    )
    if account_id is not None:
        stmt = stmt.where(WhatsappChannel.account_id == account_id)
    return [(ch, ib) for ch, ib in (await session.exec(stmt)).all()]


async def sync_recent_costs(session: AsyncSession, *, days: int = 3) -> int:
    """Worker job: the last ``days`` days for every number. Meta's figures
    settle a while after delivery, so recent days are fetched again."""
    from app.core.errors import ChatwootHTTPException

    until = datetime.now(UTC).date()
    since = until - timedelta(days=days)
    total = 0
    for channel, inbox in await cloud_numbers(session):
        try:
            async with session.begin_nested():
                total += await sync_costs(
                    session, channel=channel, inbox=inbox, since=since, until=until
                )
        except ChatwootHTTPException as exc:
            log.warning(
                "usage.whatsapp.sync_failed inbox_id=%s detail=%s", inbox.id, exc.detail
            )
        except Exception:
            log.exception("usage.whatsapp.sync_failed inbox_id=%s", inbox.id)
    return total


__all__ = ["cloud_numbers", "record_message_pricing", "sync_costs", "sync_recent_costs"]
