"""ARQ task + scheduler glue for Instagram publishing.

Two entry points:

  * :func:`publish_instagram_post_task` — the ARQ task body. Thin
    wrapper that opens a session and calls
    ``publishing_service.publish_post``. Enqueued two ways:
      1. Immediately by the REST endpoint when ``scheduled_for`` is null.
      2. By :func:`fire_due_instagram_posts` when a scheduled post
         comes due.

  * :func:`fire_due_instagram_posts` — called from the Phase 10.1
    ``tick_5min`` scheduler. SELECTs pending posts whose
    ``scheduled_for <= now()`` and enqueues the task per match.

Container creation happens inside ``publish_post`` (the task body),
NOT here — Meta containers expire after 24h so we defer creation to
fire time.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.instagram.models import InstagramPost

log = logging.getLogger(__name__)


async def fire_due_instagram_posts(session: AsyncSession) -> list[int]:
    """Find pending posts whose scheduled time has passed and enqueue
    each for publishing.

    Returns the list of post_ids enqueued (informational — the
    scheduler logs the count). Posts with ``scheduled_for IS NULL``
    are NOT picked up here — those were enqueued immediately by the
    REST endpoint at create time.
    """
    now = datetime.now(UTC)
    stmt = select(InstagramPost).where(
        InstagramPost.state == "pending",
        InstagramPost.scheduled_for.is_not(None),  # type: ignore[union-attr]
        InstagramPost.scheduled_for <= now,  # type: ignore[operator]
    )
    rows = list((await session.exec(stmt)).all())
    enqueued: list[int] = []
    for post in rows:
        if post.id is None:
            continue
        await enqueue_publish(post.id)
        enqueued.append(post.id)
        log.info(
            "instagram.scheduler.fired post_id=%s scheduled_for=%s",
            post.id,
            post.scheduled_for,
        )
    return enqueued


async def enqueue_publish(post_id: int) -> None:
    """Enqueue the publish task on the ARQ queue.

    Falls back to a direct in-process run when no ARQ pool is
    configured (e.g. local dev without a worker). The fallback keeps
    the dashboard usable in environments that don't run the worker —
    publishing just happens synchronously in the request instead.
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    settings = get_settings()
    try:
        pool = await create_pool(
            RedisSettings.from_dsn(settings.arq_redis_url)
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "instagram.enqueue.no_pool post_id=%s err=%s — running inline",
            post_id,
            exc,
        )
        await _run_inline(post_id)
        return
    try:
        await pool.enqueue_job("publish_instagram_post_task", post_id)
    finally:
        await pool.aclose()


async def _run_inline(post_id: int) -> None:
    """Synchronous fallback — open a session + publish now."""
    from app.domains.instagram.context import open_publish_session
    from app.domains.instagram.publishing_service import publish_post

    async with open_publish_session() as session:
        await publish_post(session, post_id=post_id)


# Throttle backoff: how long to defer a retry, and how many times.
THROTTLE_RETRY_BACKOFF_SECONDS = 900  # 15 min — Meta windows are coarse
THROTTLE_MAX_RETRIES = 3


async def publish_instagram_post_task(
    ctx: dict[str, Any], post_id: int
) -> dict[str, Any]:
    """ARQ task body. ``ctx`` is ARQ's per-job context.

    On a Meta throttle (error codes 4 / 17 / 80001 / 80002) the post is
    reset to ``pending`` and the job is retried with a coarse backoff,
    up to ``THROTTLE_MAX_RETRIES`` attempts. Other failures are
    terminal (the row stays ``failed`` for the operator to inspect).
    """
    from app.domains.instagram.context import open_publish_session
    from app.domains.instagram.publisher import is_throttle_error
    from app.domains.instagram.publishing_service import (
        publish_post,
        reset_for_retry,
    )

    async with open_publish_session() as session:
        post = await publish_post(session, post_id=post_id)

        if (
            post.state == "failed"
            and is_throttle_error(post.error_code)
            and ctx.get("job_try", 1) <= THROTTLE_MAX_RETRIES
        ):
            await reset_for_retry(session, post=post)
            log.warning(
                "instagram.publish.throttled post_id=%s code=%s try=%s "
                "— deferring retry",
                post_id,
                post.error_code,
                ctx.get("job_try"),
            )
            from arq.worker import Retry

            raise Retry(defer=THROTTLE_RETRY_BACKOFF_SECONDS)

        return {
            "post_id": post_id,
            "state": post.state,
            "ig_media_id": post.ig_media_id,
        }


__all__ = [
    "enqueue_publish",
    "fire_due_instagram_posts",
    "publish_instagram_post_task",
]
