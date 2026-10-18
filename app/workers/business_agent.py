"""ARQ task that hands a resolved WhatsApp conversation back to Meta's AI.

Queued by :mod:`app.domains.whatsapp.listener` on resolve, so the resolve
request never waits on Meta (bulk resolve would otherwise call Meta once
per conversation, holding each row's lock). Deferred a few seconds so the
resolve has committed; the task re-reads the conversation and gives up if
it was reopened in between.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

log = logging.getLogger(__name__)

# Long enough for the resolving request to commit.
_RELEASE_DELAY = timedelta(seconds=5)


async def enqueue_release_to_ai(*, conversation_id: int) -> None:
    """Queue the release. Falls back to running it inline with no worker,
    like ``instagram_autoreply.enqueue_autoreply``."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    try:
        pool = await create_pool(
            RedisSettings.from_dsn(get_settings().arq_redis_url)
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "whatsapp.release_to_ai.no_pool conversation=%s err=%s — running inline",
            conversation_id,
            exc,
        )
        await release_to_ai_task({}, conversation_id)
        return
    try:
        await pool.enqueue_job(
            "release_to_ai_task", conversation_id, _defer_by=_RELEASE_DELAY
        )
    finally:
        await pool.aclose()


async def release_to_ai_task(
    ctx: dict[str, Any], conversation_id: int
) -> dict[str, Any]:
    """Run :func:`release_resolved_conversation` in the task's own session."""
    from app.core.db import get_session_factory
    from app.domains.whatsapp.business_agent import (
        release_resolved_conversation,
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
        try:
            outcome = await release_resolved_conversation(
                session, conversation_id=conversation_id
            )
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception(
                "whatsapp.release_to_ai.failed conversation=%s", conversation_id
            )
            outcome = "error"
    log.info(
        "whatsapp.release_to_ai conversation=%s outcome=%s",
        conversation_id,
        outcome,
    )
    return {"conversation_id": conversation_id, "outcome": outcome}


__all__ = ["enqueue_release_to_ai", "release_to_ai_task"]
