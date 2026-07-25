"""Help-Center article embedding indexing + semantic search.

Ports the enterprise ``Enterprise::Concerns::Article`` embedding path:

  * :func:`reindex_article` — expand an article into search terms
    (``gpt-4o``), embed each, and replace the article's stored embeddings.
    Enqueued off the article create/update path via
    :func:`enqueue_reindex_article` → :func:`reindex_article_task` (ARQ),
    so the request never blocks on OpenAI.
  * :func:`vector_search` — embed the query and return the articles whose
    term embeddings are the nearest cosine neighbours, honouring the same
    portal/locale/category/status filters as the ILIKE path.

All of this is gated on ``settings.openai_api_key`` (via
:func:`app.core.llm.embedding_search_enabled`); with no key configured the
functions no-op and callers stay on ILIKE search.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.llm import (
    LlmError,
    embed_text,
    embedding_search_enabled,
    generate_search_terms,
)
from app.domains.portals.models import (
    ARTICLE_STATUS_PUBLISHED,
    Article,
    ArticleEmbedding,
    Category,
)

log = logging.getLogger(__name__)

# How many nearest term-embeddings to scan before de-duplicating down to
# distinct articles. Chatwoot limits to 5 embeddings; we scan a few more so
# a single article's terms can't crowd out the result set.
_NEIGHBOUR_SCAN = 50


async def reindex_article(session: AsyncSession, *, article_id: int) -> int:
    """Regenerate an article's term embeddings. Returns the count written.

    Best-effort: an OpenAI failure logs and leaves the *old* embeddings in
    place (we only delete once new terms are in hand). No-ops when the
    feature is off or the article is gone.
    """
    if not embedding_search_enabled():
        return 0
    article = await session.get(Article, article_id)
    if article is None:
        return 0

    try:
        terms = await generate_search_terms(
            title=article.title or "",
            description=article.description,
            content=article.content,
        )
    except LlmError as exc:
        log.warning(
            "portals.embeddings.terms_failed article_id=%s err=%s",
            article_id,
            exc,
        )
        return 0

    # Embed first; only swap the stored rows once we have new vectors, so a
    # mid-way OpenAI error can't leave the article un-searchable.
    new_rows: list[ArticleEmbedding] = []
    for term in terms:
        try:
            vector = await embed_text(term)
        except LlmError as exc:
            log.warning(
                "portals.embeddings.embed_failed article_id=%s err=%s",
                article_id,
                exc,
            )
            return 0
        if not vector:
            continue
        new_rows.append(
            ArticleEmbedding(article_id=article_id, term=term, embedding=vector)
        )

    existing = (
        await session.exec(
            select(ArticleEmbedding).where(
                ArticleEmbedding.article_id == article_id
            )
        )
    ).all()
    for row in existing:
        await session.delete(row)
    for row in new_rows:
        session.add(row)
    await session.flush()
    return len(new_rows)


async def _candidate_article_ids(
    session: AsyncSession,
    *,
    portal_id: int,
    locale: str | None,
    category_slug: str | None,
    status: int,
) -> list[int]:
    stmt = select(Article.id).where(
        Article.portal_id == portal_id,
        Article.status == status,
    )
    if locale is not None:
        stmt = stmt.where(Article.locale == locale)
    if category_slug is not None:
        stmt = stmt.join(
            Category, Category.id == Article.category_id
        ).where(Category.slug == category_slug)
    return [i for i in (await session.exec(stmt)).all() if i is not None]


async def vector_search(
    session: AsyncSession,
    *,
    portal_id: int,
    query: str,
    locale: str | None = None,
    category_slug: str | None = None,
    status: int = ARTICLE_STATUS_PUBLISHED,
    limit: int = 5,
) -> list[Article]:
    """Return up to ``limit`` articles by cosine nearest-neighbour on their
    term embeddings, ordered most-relevant first.

    Raises :class:`~app.core.llm.LlmError` if the query embedding call
    fails — the public router catches it and falls back to ILIKE.
    """
    candidate_ids = await _candidate_article_ids(
        session,
        portal_id=portal_id,
        locale=locale,
        category_slug=category_slug,
        status=status,
    )
    if not candidate_ids:
        return []

    query_vector = await embed_text(query)
    if not query_vector:
        return []

    distance = ArticleEmbedding.embedding.cosine_distance(  # type: ignore[attr-defined]
        query_vector
    )
    rows = (
        await session.exec(
            select(ArticleEmbedding.article_id)
            .where(
                ArticleEmbedding.article_id.in_(candidate_ids),  # type: ignore[attr-defined]
                ArticleEmbedding.embedding.is_not(None),  # type: ignore[attr-defined]
            )
            .order_by(distance)
            .limit(_NEIGHBOUR_SCAN)
        )
    ).all()

    # De-dup to distinct articles, preserving nearest-first order.
    ordered_ids: list[int] = []
    for aid in rows:
        if aid is not None and aid not in ordered_ids:
            ordered_ids.append(aid)
        if len(ordered_ids) >= limit:
            break
    if not ordered_ids:
        return []

    articles = (
        await session.exec(
            select(Article).where(Article.id.in_(ordered_ids))  # type: ignore[attr-defined]
        )
    ).all()
    by_id = {a.id: a for a in articles}
    return [by_id[i] for i in ordered_ids if i in by_id]


async def enqueue_reindex_article(article_id: int) -> None:
    """Best-effort enqueue of the reindex task — never raises (dev without
    a worker or Redis just skips indexing; search stays on ILIKE)."""
    if not embedding_search_enabled():
        return
    from arq import create_pool
    from arq.connections import RedisSettings

    settings = get_settings()
    # Article save is interactive — don't let a momentarily-down Redis stall
    # it. Fail fast (arq's default is 5 retries with backoff ≈ 5s) and skip
    # indexing; search just stays on ILIKE until the next save.
    redis_settings = RedisSettings.from_dsn(settings.arq_redis_url)
    redis_settings.conn_retries = 1
    redis_settings.conn_retry_delay = 0
    try:
        pool = await create_pool(redis_settings)
        try:
            await pool.enqueue_job("reindex_article_task", article_id)
        finally:
            await pool.aclose()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "portals.embeddings.enqueue_failed article_id=%s err=%s",
            article_id,
            exc,
        )


async def enqueue_reindex_portal(
    session: AsyncSession, *, portal_id: int
) -> int:
    """Enqueue a reindex for every article in the portal. Returns the count
    enqueued (0 when the feature is off, the portal is empty, or Redis is
    unreachable). One pool for the whole batch."""
    if not embedding_search_enabled():
        return 0
    ids = [
        i
        for i in (
            await session.exec(
                select(Article.id).where(Article.portal_id == portal_id)
            )
        ).all()
        if i is not None
    ]
    if not ids:
        return 0

    from arq import create_pool
    from arq.connections import RedisSettings

    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.arq_redis_url)
    redis_settings.conn_retries = 1
    redis_settings.conn_retry_delay = 0
    enqueued = 0
    try:
        pool = await create_pool(redis_settings)
        try:
            for article_id in ids:
                await pool.enqueue_job("reindex_article_task", article_id)
                enqueued += 1
        finally:
            await pool.aclose()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "portals.embeddings.reindex_portal_failed portal_id=%s err=%s",
            portal_id,
            exc,
        )
    return enqueued


async def reindex_article_task(
    ctx: dict[str, Any], article_id: int
) -> dict[str, Any]:
    """ARQ task body — opens a session (reusing the worker engine on
    ``ctx``) and reindexes the article."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = ctx.get("engine")
    if engine is None:
        engine = create_async_engine(
            get_settings().database_url, pool_pre_ping=True
        )
    sessionmaker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with sessionmaker() as session:
        written = await reindex_article(session, article_id=article_id)
        await session.commit()
    return {"article_id": article_id, "embeddings": written}


__all__ = [
    "enqueue_reindex_article",
    "enqueue_reindex_portal",
    "reindex_article",
    "reindex_article_task",
    "vector_search",
]
