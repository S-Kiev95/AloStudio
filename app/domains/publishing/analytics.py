"""Publishing analytics — cached post metrics, daily channel snapshots and
the summary the dashboard and the agent read.

Figures are cached rather than fetched live (networks rate-limit insights;
same reasoning as ``app.domains.ads``): an hourly job refreshes the posts of
the last 30 days that haven't been refreshed for a while (newer posts more
often), and a daily job takes one snapshot per channel — today's follower
count plus the per-day figures of the last few complete days, re-read
because networks keep settling them. Every network call goes through the
adapter registry, so nothing here names a network.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.publishing import service as svc
from app.domains.publishing.adapters import (
    MetricsResult,
    adapter_for_network,
    target_text,
)
from app.domains.publishing.models import (
    CHANNEL_METRIC_KEYS,
    CHANNEL_STATUS_ACTIVE,
    METRIC_KEYS,
    TARGET_STATE_PUBLISHED,
    ChannelMetricSnapshot,
    Publication,
    PublicationTarget,
    PublishingChannel,
)
from app.domains.publishing.presenters import present_channel

log = logging.getLogger(__name__)

# Posts keep gathering engagement for a few weeks; older ones are left as
# last read. Most of it comes in the first days, so those are re-read more
# often.
POST_WINDOW = timedelta(days=30)
NEW_POST_AGE = timedelta(days=3)
NEW_POST_STALE_AFTER = timedelta(hours=6)
POST_STALE_AFTER = timedelta(hours=24)
SYNC_BATCH_SIZE = 200
# A manual refresh inside this window keeps the figures just read.
REFRESH_COOLDOWN = timedelta(minutes=5)
# Complete days re-read on each channel snapshot.
CHANNEL_LOOKBACK_DAYS = 3
MAX_RANGE = timedelta(days=366)
TOP_POSTS = 5


def _interactions(metrics: dict[str, Any]) -> int:
    if isinstance(metrics.get("interactions"), int):
        return metrics["interactions"]
    return sum(
        metrics.get(k, 0) for k in ("likes", "comments", "shares", "saves")
        if isinstance(metrics.get(k), int)
    )


def _sum(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for metrics in rows:
        for key in keys:
            value = metrics.get(key)
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value
    return totals


# ---------------------------------------------------------------------------
# Refreshing
# ---------------------------------------------------------------------------
async def refresh_target_metrics(
    session: AsyncSession, target: PublicationTarget
) -> bool:
    """Read one published target's figures from its network. On failure the
    last good figures stay and ``metrics_error`` says why. Returns True when
    fresh figures were stored."""
    adapter = adapter_for_network(target.network)
    if adapter is None or target.state != TARGET_STATE_PUBLISHED:
        return False
    try:
        result = await adapter.fetch_post_metrics(session, target)
    except Exception:
        log.exception("publishing.metrics.post_failed target_id=%s", target.id)
        result = MetricsResult(
            ok=False, error_message="Error inesperado al leer las estadísticas."
        )
    if result is not None and result.ok:
        # An empty read (nothing new from the network) keeps what we had.
        if result.metrics:
            target.metrics = result.metrics
        target.metrics_error = None
    elif result is not None:
        target.metrics_error = result.error_message
    # Stamped on failure, and when the network has no figures to give, so
    # such a post isn't picked again on every run.
    target.metrics_updated_at = datetime.now(UTC)
    session.add(target)
    await session.flush()
    return result is not None and result.ok


async def refresh_publication_metrics(
    session: AsyncSession, *, publication: Publication
) -> None:
    """On demand: refresh every published target of one publication, except
    those read in the last few minutes (a repeated click costs quota)."""
    recent = datetime.now(UTC) - REFRESH_COOLDOWN
    targets = (
        await svc.targets_by_publication(
            session, publication_ids=[publication.id]  # type: ignore[list-item]
        )
    )[publication.id]  # type: ignore[index]
    for target in targets:
        if target.metrics_updated_at is None or target.metrics_updated_at < recent:
            await refresh_target_metrics(session, target)


async def sync_post_metrics(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    batch_size: int = SYNC_BATCH_SIZE,
) -> int:
    """Refresh the recent posts whose figures are missing or stale, least
    recently read first, committing each one so a failure only loses that
    post. Returns how many got fresh figures."""
    now = now or datetime.now(UTC)
    updated_at = col(PublicationTarget.metrics_updated_at)
    published_at = col(PublicationTarget.published_at)
    target_ids = (
        await session.exec(
            select(PublicationTarget.id)
            .where(
                PublicationTarget.state == TARGET_STATE_PUBLISHED,
                col(PublicationTarget.external_id).is_not(None),
                published_at >= now - POST_WINDOW,
                updated_at.is_(None)
                | (updated_at < now - POST_STALE_AFTER)
                | (
                    (published_at >= now - NEW_POST_AGE)
                    & (updated_at < now - NEW_POST_STALE_AFTER)
                ),
            )
            .order_by(updated_at.asc().nulls_first())
            .limit(batch_size)
        )
    ).all()
    refreshed = 0
    for target_id in target_ids:
        try:
            target = await session.get(PublicationTarget, target_id)
            if target is not None and await refresh_target_metrics(session, target):
                refreshed += 1
            await session.commit()
        except Exception:
            # One post must not sink the rest of the batch.
            await session.rollback()
            log.exception("publishing.metrics.post_store_failed target_id=%s", target_id)
    return refreshed


async def snapshot_channels(
    session: AsyncSession, *, today: date | None = None
) -> int:
    """Store today's follower count of every active publishing channel that
    has no snapshot today yet, and merge in the per-day figures of the last
    :data:`CHANNEL_LOOKBACK_DAYS` complete days. Each channel is committed
    on its own. Returns how many channels were stored."""
    today = today or datetime.now(UTC).date()
    days = [today - timedelta(days=n) for n in range(1, CHANNEL_LOOKBACK_DAYS + 1)]
    # Inboxes connected since the last listing still get their channel.
    await svc.sync_inbox_channels(session)
    await session.commit()
    done = select(ChannelMetricSnapshot.channel_id).where(
        ChannelMetricSnapshot.date == today
    )
    channel_ids = (
        await session.exec(
            select(PublishingChannel.id)
            .where(
                PublishingChannel.status == CHANNEL_STATUS_ACTIVE,
                col(PublishingChannel.id).not_in(done),
            )
            .order_by(col(PublishingChannel.id))
        )
    ).all()
    stored = 0
    for channel_id in channel_ids:
        try:
            channel = await session.get(PublishingChannel, channel_id)
            adapter = adapter_for_network(channel.network) if channel is not None else None
            if channel is None or adapter is None:
                continue
            result = await adapter.fetch_channel_metrics(session, channel, days=days)
            if result is None or not result.ok:
                if result is not None and result.error_message:
                    log.info(
                        "publishing.metrics.channel_unavailable channel_id=%s reason=%s",
                        channel_id,
                        result.error_message,
                    )
                continue
            rows = {day: dict(figures) for day, figures in result.daily.items()}
            if result.metrics:
                rows[today] = {**rows.get(today, {}), **result.metrics}
            for day, figures in rows.items():
                await _merge_snapshot(session, channel=channel, day=day, metrics=figures)
            await session.commit()
            stored += int(bool(rows))
        except Exception:
            # One channel must not sink the rest.
            await session.rollback()
            log.exception("publishing.metrics.channel_failed channel_id=%s", channel_id)
    return stored


async def _merge_snapshot(
    session: AsyncSession,
    *,
    channel: PublishingChannel,
    day: date,
    metrics: dict[str, int],
) -> None:
    """Upsert one channel-day; figures already stored for that day and not
    read again (that day's follower count, say) are kept."""
    now = datetime.now(UTC)
    stmt = pg_insert(ChannelMetricSnapshot).values(
        account_id=channel.account_id,
        channel_id=channel.id,
        network=channel.network,
        date=day,
        metrics=metrics,
        created_at=now,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uniq_channel_metric_snapshots_channel_date",
        set_={
            "metrics": ChannelMetricSnapshot.__table__.c.metrics.op("||")(  # type: ignore[attr-defined]
                stmt.excluded.metrics
            ),
            "updated_at": now,
        },
    )
    await session.exec(stmt)  # type: ignore[call-overload]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
async def analytics_summary(
    session: AsyncSession,
    *,
    account_id: int,
    starts_from: datetime,
    starts_to: datetime,
    channel_id: int | None = None,
) -> dict[str, Any]:
    """Totals, per-channel figures and growth, and the best posts of the
    period (posts by publish date, ``from`` inclusive, ``to`` exclusive;
    channel days that overlap the period, in UTC)."""
    if starts_to <= starts_from or starts_to - starts_from > MAX_RANGE:
        raise svc._unprocessable("El período debe ir de un momento a otro posterior, hasta un año.")
    first_day = starts_from.astimezone(UTC).date()
    last_day = (starts_to - timedelta(microseconds=1)).astimezone(UTC).date()
    stmt = (
        select(PublicationTarget, Publication)
        .join(Publication, Publication.id == PublicationTarget.publication_id)  # type: ignore[arg-type]
        .where(
            PublicationTarget.account_id == account_id,
            PublicationTarget.state == TARGET_STATE_PUBLISHED,
            PublicationTarget.published_at >= starts_from,  # type: ignore[operator]
            PublicationTarget.published_at < starts_to,  # type: ignore[operator]
        )
    )
    if channel_id is not None:
        stmt = stmt.where(PublicationTarget.channel_id == channel_id)
    rows = list((await session.exec(stmt)).all())

    snapshot_stmt = (
        select(ChannelMetricSnapshot)
        .where(
            ChannelMetricSnapshot.account_id == account_id,
            ChannelMetricSnapshot.date >= first_day,
            ChannelMetricSnapshot.date <= last_day,
        )
        .order_by(ChannelMetricSnapshot.date)  # type: ignore[arg-type]
    )
    snapshots = list((await session.exec(snapshot_stmt)).all())

    channels = []
    for channel in await svc.list_channels(session, account_id=account_id):
        if channel_id is not None and channel.id != channel_id:
            continue
        posts = [t.metrics or {} for t, _ in rows if t.channel_id == channel.id]
        series = [s for s in snapshots if s.channel_id == channel.id]
        followers = [
            s.metrics["followers"]
            for s in series
            if isinstance(s.metrics.get("followers"), int)
        ]
        channels.append(
            {
                "channel": present_channel(channel),
                "posts": len(posts),
                "metrics": _sum(posts, METRIC_KEYS),
                "followers": followers[-1] if followers else None,
                "followers_change": (
                    followers[-1] - followers[0] if len(followers) > 1 else None
                ),
                "series": [
                    {
                        "date": s.date.isoformat(),
                        **{
                            k: v
                            for k, v in s.metrics.items()
                            if k in CHANNEL_METRIC_KEYS
                        },
                    }
                    for s in series
                ],
            }
        )

    presented = {c["channel"]["id"]: c["channel"] for c in channels}
    best = sorted(rows, key=lambda r: _interactions(r[0].metrics or {}), reverse=True)
    return {
        "from": starts_from.isoformat(),
        "to": starts_to.isoformat(),
        "totals": {
            "posts": len(rows),
            **_sum([t.metrics or {} for t, _ in rows], METRIC_KEYS),
        },
        "channels": channels,
        "top_posts": [
            {
                "publication_id": publication.id,
                "target_id": target.id,
                "channel": presented.get(target.channel_id),
                "content": target_text(publication, target)[:280],
                "permalink": target.permalink,
                "published_at": target.published_at.isoformat()
                if target.published_at
                else None,
                "metrics": target.metrics or {},
            }
            for target, publication in best[:TOP_POSTS]
        ],
    }


__all__ = [
    "analytics_summary",
    "refresh_publication_metrics",
    "refresh_target_metrics",
    "snapshot_channels",
    "sync_post_metrics",
]
