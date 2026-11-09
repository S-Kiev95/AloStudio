"""Backfill of local-model (EmbeddingGemma 2) vectors — F9 migration.

New saves already write both providers' vectors; this fills in the rows
written before the local model existed:

* prepared Instagram answers with ``embedding_gemma IS NULL``, embedded in
  batches with the same ``classification`` task the matcher uses;
* Help-Center articles with no ``model="gemma"`` row, embedded whole (no
  gpt-4o call, unlike a full reindex).

Resumable by construction: every pass picks only what is still missing, so
it can be stopped and enqueued again. Enqueued by ``scripts/embeddings_gemma.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import exists
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.embeddings import (
    MODEL_GEMMA,
    TASK_CLASSIFICATION,
    embed_gemma,
    gemma_enabled,
)
from app.core.llm import LlmError
from app.domains.instagram.autoreply_models import InstagramCommentReply
from app.domains.portals.embeddings import reindex_article_gemma
from app.domains.portals.models import Article, ArticleEmbedding, Portal

log = logging.getLogger(__name__)

BATCH_SIZE = 32


async def backfill_comment_replies(
    session: AsyncSession, *, account_id: int | None = None
) -> int:
    """Embed every prepared answer still missing its local vector.

    Returns how many were written. Stops at the first failed batch (the
    service is down, say): what was written stays, the rest is picked up
    by the next run."""
    written = 0
    failed_ids: set[int] = set()
    while True:
        stmt = select(InstagramCommentReply).where(
            InstagramCommentReply.embedding_gemma.is_(None)  # type: ignore[union-attr]
        )
        if account_id is not None:
            stmt = stmt.where(InstagramCommentReply.account_id == account_id)
        if failed_ids:
            stmt = stmt.where(InstagramCommentReply.id.not_in(failed_ids))  # type: ignore[union-attr]
        rows = list(
            (await session.exec(stmt.order_by(InstagramCommentReply.id).limit(BATCH_SIZE))).all()
        )
        if not rows:
            return written
        try:
            vectors = await embed_gemma(
                [r.trigger for r in rows], task=TASK_CLASSIFICATION
            )
        except LlmError as exc:
            log.warning("embeddings.backfill.replies_failed err=%s", exc)
            return written
        for row, vector in zip(rows, vectors, strict=True):
            if vector:
                row.embedding_gemma = vector
                session.add(row)
                written += 1
            elif row.id is not None:
                # Blank trigger: nothing to embed, never retried this run.
                failed_ids.add(row.id)
        await session.commit()


async def backfill_articles(
    session: AsyncSession, *, account_id: int | None = None
) -> int:
    """Embed every article that has no local-model row yet."""
    has_gemma_row = exists().where(
        ArticleEmbedding.article_id == Article.id,
        ArticleEmbedding.model == MODEL_GEMMA,
    )
    stmt = select(Article.id).where(~has_gemma_row)
    if account_id is not None:
        stmt = stmt.join(Portal, Portal.id == Article.portal_id).where(
            Portal.account_id == account_id
        )
    ids = [i for i in (await session.exec(stmt.order_by(Article.id))).all() if i is not None]
    written = 0
    for article_id in ids:
        written += await reindex_article_gemma(session, article_id=article_id)
        await session.commit()
    return written


async def backfill_gemma_embeddings_task(
    ctx: dict[str, Any], account_id: int | None = None
) -> dict[str, Any]:
    """ARQ task body. ``account_id`` None means every account."""
    if not gemma_enabled():
        return {"skipped": "embeddings_service_url is not set"}
    engine: AsyncEngine | None = ctx.get("engine")
    if engine is None:
        engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with sessionmaker() as session:
        replies = await backfill_comment_replies(session, account_id=account_id)
        articles = await backfill_articles(session, account_id=account_id)
    log.info(
        "embeddings.backfill.done account_id=%s replies=%s articles=%s",
        account_id,
        replies,
        articles,
    )
    return {"account_id": account_id, "replies": replies, "articles": articles}


__all__ = [
    "backfill_articles",
    "backfill_comment_replies",
    "backfill_gemma_embeddings_task",
]
