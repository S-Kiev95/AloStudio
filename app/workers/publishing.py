"""ARQ task + scheduler glue for multi-network publishing.

Two entry points, mirroring :mod:`app.workers.instagram`:

  * :func:`fire_due_publications` — called from the ``tick_5min``
    scheduler. Claims every scheduled publication whose time has come
    (the claim is a conditional update, so two ticks never double-fire)
    and enqueues :func:`publish_publication_task` for each.

  * :func:`publish_publication_task` — the ARQ task body. Publishes every
    pending target through its network adapter. Targets that failed with
    a retryable error (rate limits, 5xx) stay pending and the job is
    retried with a coarse backoff, up to ``RETRY_MAX_TRIES`` attempts.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

log = logging.getLogger(__name__)

RETRY_BACKOFF_SECONDS = 900  # 15 min — network rate windows are coarse
RETRY_MAX_TRIES = 3
# Several targets, each possibly a video Meta has to process.
JOB_TIMEOUT_SECONDS = 1800
# A batch of posts (or every channel) read one after the other; kept under
# the hour so two hourly runs never overlap.
METRICS_JOB_TIMEOUT_SECONDS = 1800
# Longer than a job (timeout) plus a retry wait (backoff), so a healthy
# job is never taken for a dead one.
STALE_AFTER = timedelta(minutes=60)


async def fire_due_publications(session: AsyncSession) -> list[int]:
    """Claim and enqueue the publications that are due, and re-enqueue the
    ones a dead job left behind. Returns the ids enqueued."""
    from app.domains.publishing import service as svc

    requeue = await svc.recover_stale_publications(
        session, older_than=STALE_AFTER
    )
    await session.commit()
    for publication_id in requeue:
        log.warning(
            "publishing.scheduler.recovered publication_id=%s", publication_id
        )

    fired: list[int] = []
    for publication_id in await svc.due_publication_ids(session):
        if not await svc.start_publishing(
            session, publication_id=publication_id
        ):
            continue
        # Commit the claim before enqueueing so the worker sees it.
        await session.commit()
        requeue.append(publication_id)

    for publication_id in requeue:
        try:
            await enqueue_publication(publication_id)
        except Exception:
            # Hand it back to the next tick instead of leaving it claimed.
            log.exception(
                "publishing.scheduler.enqueue_failed publication_id=%s",
                publication_id,
            )
            await svc.release_claim(session, publication_id=publication_id)
            await session.commit()
            continue
        fired.append(publication_id)
        log.info("publishing.scheduler.fired publication_id=%s", publication_id)
    return fired


async def enqueue_publication(publication_id: int) -> None:
    """Enqueue the publish task, or run it inline when no ARQ pool is
    reachable (local dev without a worker), like Instagram does."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    try:
        pool = await create_pool(
            RedisSettings.from_dsn(get_settings().arq_redis_url)
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "publishing.enqueue.no_pool publication_id=%s err=%s — running inline",
            publication_id,
            exc,
        )
        await _run_inline(publication_id)
        return
    try:
        await pool.enqueue_job("publish_publication_task", publication_id)
    finally:
        await pool.aclose()


def _session_factory(ctx: dict[str, Any] | None) -> async_sessionmaker[AsyncSession]:
    """The worker's engine when running under ARQ, the app's otherwise. The
    inline fallback runs inside the request, on the loop the app's pooled
    engine belongs to, so it doesn't need a NullPool engine of its own."""
    from app.core.db import get_session_factory

    engine = ctx.get("engine") if isinstance(ctx, dict) else None
    if engine is None:
        return get_session_factory()
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def _publish(
    ctx: dict[str, Any] | None, publication_id: int, *, final_attempt: bool
) -> tuple[bool, str | None]:
    from app.domains.publishing.models import Publication
    from app.domains.publishing.service import publish_pending_targets

    async with _session_factory(ctx)() as session:
        try:
            retry_needed = await publish_pending_targets(
                session,
                publication_id=publication_id,
                final_attempt=final_attempt,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        publication = await session.get(Publication, publication_id)
        return retry_needed, publication.state if publication else None


async def _run_inline(publication_id: int) -> None:
    await _publish(None, publication_id, final_attempt=True)


async def publish_publication_task(
    ctx: dict[str, Any], publication_id: int
) -> dict[str, Any]:
    """ARQ task body. ``ctx`` is ARQ's per-job context."""
    job_try = ctx.get("job_try", 1)
    retry_needed, state = await _publish(
        ctx, publication_id, final_attempt=job_try >= RETRY_MAX_TRIES
    )

    # Raised after the session committed, so the attempt is recorded.
    if retry_needed:
        log.warning(
            "publishing.publish.retry publication_id=%s try=%s — deferring",
            publication_id,
            job_try,
        )
        from arq.worker import Retry

        raise Retry(defer=RETRY_BACKOFF_SECONDS)

    return {"publication_id": publication_id, "state": state}


async def sync_publishing_metrics_task(ctx: dict[str, Any]) -> dict[str, int]:
    """Hourly: refresh the figures of recent posts. Each post is committed on
    its own inside :func:`analytics.sync_post_metrics`."""
    from app.domains.publishing import analytics

    async with _session_factory(ctx)() as session:
        posts = await analytics.sync_post_metrics(session)
    log.info("publishing.metrics.posts_synced posts=%s", posts)
    return {"posts": posts}


async def snapshot_publishing_channels_task(ctx: dict[str, Any]) -> dict[str, int]:
    """Daily: today's follower count and the last days' figures of each
    publishing channel. Once a day, so a channel that fails isn't retried
    every hour against its rate limit."""
    from app.domains.publishing import analytics

    async with _session_factory(ctx)() as session:
        channels = await analytics.snapshot_channels(session)
    log.info("publishing.metrics.channels_snapshotted channels=%s", channels)
    return {"channels": channels}


__all__ = [
    "enqueue_publication",
    "fire_due_publications",
    "publish_publication_task",
    "snapshot_publishing_channels_task",
    "sync_publishing_metrics_task",
]
