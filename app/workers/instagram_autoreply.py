"""ARQ task that posts an automatic reply to an Instagram comment.

Separate from the webhook so Meta gets its 200 immediately — a slow
webhook is retried by Meta, and a retried comment delivery would mean a
second public reply.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

log = logging.getLogger(__name__)


async def enqueue_autoreply(*, comment_id: int, text: str) -> None:
    """Queue the reply. Falls back to sending inline with no worker.

    Mirrors ``instagram.enqueue_publish``: an environment without a worker
    (local dev) still behaves correctly, just synchronously.
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    try:
        pool = await create_pool(
            RedisSettings.from_dsn(get_settings().arq_redis_url)
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "instagram.autoreply.no_pool comment_id=%s err=%s — running inline",
            comment_id,
            exc,
        )
        await send_comment_autoreply_task({}, comment_id, text)
        return
    await pool.enqueue_job("send_comment_autoreply_task", comment_id, text)


async def send_comment_autoreply_task(
    ctx: dict[str, Any], comment_id: int, text: str
) -> dict[str, Any]:
    """Post ``text`` as a reply to ``comment_id``.

    The comment was already marked replied by the caller, so a failure here
    leaves it unanswered rather than answered twice. That asymmetry is
    deliberate: a human can still answer a missed comment, but a duplicate
    reply is public and cannot be taken back cleanly.
    """
    from sqlmodel import select

    from app.core.db import get_session_factory
    from app.domains.inboxes.models import InstagramChannel
    from app.domains.instagram.comments_client import create_reply
    from app.domains.instagram.graph import graph_host, host_for_login_type
    from app.domains.instagram.models import (
        InstagramChannelSetting,
        InstagramComment,
    )

    engine = ctx.get("engine") if isinstance(ctx, dict) else None
    factory = (
        async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        if engine is not None
        else get_session_factory()
    )

    async with factory() as session:
        comment = await session.get(InstagramComment, comment_id)
        if comment is None:
            return {"sent": False, "reason": "comment_gone"}
        channel = await session.get(
            InstagramChannel, comment.channel_instagram_id
        )
        if channel is None:
            return {"sent": False, "reason": "channel_gone"}
        setting = (
            await session.exec(
                select(InstagramChannelSetting).where(
                    InstagramChannelSetting.channel_instagram_id == channel.id
                )
            )
        ).first()

        # Facebook Login and Instagram Login publish through different Graph
        # hosts; the client reads the host from a task-local var.
        with graph_host(
            host_for_login_type(setting.login_type if setting else "facebook")
        ):
            result = await create_reply(
                channel,
                ig_comment_id=comment.ig_comment_id,
                message=text,
            )

    ok = bool(getattr(result, "ok", result))
    log.info(
        "instagram.autoreply.sent comment=%s ok=%s",
        comment_id,
        ok,
    )
    return {"sent": ok, "comment_id": comment_id}


__all__ = ["enqueue_autoreply", "send_comment_autoreply_task"]
