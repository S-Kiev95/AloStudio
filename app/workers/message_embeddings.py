"""Cron: keep message vectors current, and backfill the old ones (F8).

Every three minutes, up to two minutes of batches. New messages get their
vector within a few minutes; an existing install's history fills in over
successive runs, newest first. Does nothing until the local embedding
service is configured, so installs without it are unaffected.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.embeddings import EmbeddingServiceError, gemma_enabled
from app.domains.conversations.message_embeddings import embed_until

log = logging.getLogger(__name__)

RUN_SECONDS = 120


async def embed_messages_task(ctx: dict[str, Any]) -> dict[str, Any]:
    if not gemma_enabled():
        return {"skipped": "embeddings_service_url is not set"}
    engine = ctx.get("engine") or create_async_engine(
        get_settings().database_url, pool_pre_ping=True
    )
    sessionmaker = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with sessionmaker() as session:
        try:
            done = await embed_until(session, seconds=RUN_SECONDS)
        except EmbeddingServiceError as exc:
            # The service restarting is not worth an alarm: the next run
            # picks up exactly where this one stopped.
            log.warning("messages.embed.unavailable err=%s", exc)
            return {"embedded": 0, "error": "service unavailable"}
    if done:
        log.info("messages.embed.done embedded=%s", done)
    return {"embedded": done}


__all__ = ["embed_messages_task"]
