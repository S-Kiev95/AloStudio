"""Sync Meta ad insights into the local cache.

Upserts on ``(account_id, ad_id, date)``. That key matters: Meta restates
recent days as attribution settles, so a nightly sync re-reads a window
that overlaps what it already stored. Inserting blindly would double the
spend of every re-read day and quietly inflate every cost figure.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.ads.client import InsightsResult, fetch_ad_insights
from app.domains.ads.models import AdInsight
from app.domains.integrations.models import (
    HOOK_STATUS_ENABLED,
    IntegrationsHook,
)

# Must match the ``IntegrationApp`` id in the integrations registry — the
# hook the admin creates from the Integrations tab is looked up by it.
META_ADS_APP_ID = "meta_ads"

log = logging.getLogger(__name__)

# Meta keeps adjusting the last few days, so a sync re-reads a trailing
# window rather than only "since the last run".
DEFAULT_LOOKBACK_DAYS = 7


async def store_insights(
    session: AsyncSession,
    *,
    account_id: int,
    result: InsightsResult,
) -> int:
    """Upsert fetched rows. Returns how many were written."""
    if not result.ok or not result.rows:
        return 0

    now = datetime.now(UTC)
    written = 0
    for row in result.rows:
        stmt = (
            pg_insert(AdInsight)
            .values(
                account_id=account_id,
                ad_id=row.ad_id,
                ad_name=row.ad_name,
                date=row.date,
                spend=row.spend,
                currency=row.currency,
                impressions=row.impressions,
                clicks=row.clicks,
                reach=row.reach,
                raw=row.raw,
                synced_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uniq_ad_insight_per_day",
                set_={
                    "ad_name": row.ad_name,
                    "spend": row.spend,
                    "currency": row.currency,
                    "impressions": row.impressions,
                    "clicks": row.clicks,
                    "reach": row.reach,
                    "raw": row.raw,
                    "synced_at": now,
                    "updated_at": now,
                },
            )
        )
        await session.exec(stmt)  # type: ignore[call-overload]
        written += 1
    return written


async def sync_ad_insights(
    session: AsyncSession,
    *,
    account_id: int,
    ad_account_id: str,
    access_token: str,
    since: date | None = None,
    until: date | None = None,
) -> int:
    """Fetch and cache one account's insights. Returns rows written.

    A failed fetch writes nothing and returns 0, leaving whatever was
    cached before intact — a blank report is worse than a stale one.
    """
    today = datetime.now(UTC).date()
    until = until or today
    since = since or (today - timedelta(days=DEFAULT_LOOKBACK_DAYS))

    result = await fetch_ad_insights(
        ad_account_id=ad_account_id,
        access_token=access_token,
        since=since,
        until=until,
    )
    if not result.ok:
        log.warning(
            "ads.sync.skipped account_id=%s code=%s msg=%s",
            account_id, result.error_code, result.error_message,
        )
        return 0

    written = await store_insights(
        session, account_id=account_id, result=result
    )
    log.info(
        "ads.sync.ok account_id=%s rows=%s range=%s..%s",
        account_id, written, since, until,
    )
    return written


def _credential_of(hook: IntegrationsHook) -> tuple[str, str] | None:
    """``(ad_account_id, access_token)`` from a meta_ads hook, or None.

    The ad account id may be stored either on ``reference_id`` (which is
    what the generic hook API fills) or inside ``settings``, so both are
    accepted rather than forcing the admin to know which one the form used.
    """
    settings = hook.settings or {}
    ad_account = (
        hook.reference_id
        or settings.get("ad_account_id")
        or settings.get("account_id")
    )
    token = hook.access_token or settings.get("access_token")
    if not ad_account or not token:
        return None
    return str(ad_account), str(token)


async def sync_all_connected_accounts(
    session: AsyncSession,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> int:
    """Sync every account with a connected, enabled meta_ads hook.

    Returns the total rows written. One account's failure never stops the
    others — a revoked token on one tenant must not blank another's report.
    """
    hooks = (
        await session.exec(
            select(IntegrationsHook).where(
                IntegrationsHook.app_id == META_ADS_APP_ID,
                IntegrationsHook.status == HOOK_STATUS_ENABLED,
            )
        )
    ).all()
    if not hooks:
        return 0

    today = datetime.now(UTC).date()
    since = today - timedelta(days=lookback_days)
    total = 0
    for hook in hooks:
        credential = _credential_of(hook)
        if credential is None or hook.account_id is None:
            log.info(
                "ads.sync.hook_incomplete hook_id=%s — needs an ad account id "
                "and a token",
                hook.id,
            )
            continue
        ad_account, token = credential
        try:
            total += await sync_ad_insights(
                session,
                account_id=hook.account_id,
                ad_account_id=ad_account,
                access_token=token,
                since=since,
                until=today,
            )
            await session.commit()
        except Exception:
            # One tenant must not sink the rest: a revoked token on one
            # account cannot be allowed to blank another account's report.
            await session.rollback()
            log.exception(
                "ads.sync.account_failed account_id=%s", hook.account_id
            )
    return total


__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "store_insights",
    "sync_ad_insights",
    "sync_all_connected_accounts",
]
