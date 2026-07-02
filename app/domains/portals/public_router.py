"""Public Help Center HTTP endpoints — no auth, slug-keyed.

Ported from:
  reference/chatwoot/app/controllers/public/api/v1/portals_controller.rb
  reference/chatwoot/app/controllers/public/api/v1/portals/articles_controller.rb
  reference/chatwoot/app/controllers/public/api/v1/portals/categories_controller.rb

Route map:

  * ``GET /hc/<slug>``                         — portal detail (404 if archived)
  * ``GET /hc/<slug>/articles[?locale=]``      — published articles only
  * ``GET /hc/<slug>/categories[?locale=]``    — categories listing

These are the JSON-returning endpoints the dashboard's Help Center
SPA + the contact-facing pages consume. The HTML rendering layer
(Rails ``layout 'portal'``) is out of scope — JSON only.

Auth: none. Archived portals 404. Only ``status=published`` articles
surface on the public side (drafts + archived stay hidden).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from sqlmodel import or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.portals.models import (
    ARTICLE_STATUS_PUBLISHED,
    Article,
    Category,
    Portal,
)
from app.domains.portals.presenters import (
    present_article,
    present_category,
    present_portal,
)

public_router = APIRouter(prefix="/hc", tags=["public-help-center"])


async def _resolve_portal(
    session: AsyncSession, slug: str
) -> Portal:
    """Find a portal by slug; 404 when missing OR archived (Rails'
    ``find_by!(slug:, archived: false)`` semantics)."""
    portal = (
        await session.exec(
            select(Portal).where(
                Portal.slug == slug, Portal.archived.is_(False)  # type: ignore[union-attr]
            )
        )
    ).first()
    if portal is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return portal


@public_router.get("/{slug}")
async def show_portal(
    slug: Annotated[str, Path()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``GET /hc/<slug>`` — the portal detail page payload."""
    portal = await _resolve_portal(session, slug)
    return present_portal(portal)


@public_router.get("/{slug}/articles")
async def index_articles(
    slug: Annotated[str, Path()],
    session: Annotated[AsyncSession, Depends(get_session)],
    locale: str | None = Query(None),
    category_slug: str | None = Query(None),
    query: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Published articles for a portal, optionally filtered by locale,
    category slug, or a free-text ``query``. Drafts + archived articles
    never surface here. ``query`` runs an ILIKE over the article's
    title/description/content — mirrors Chatwoot's ``Article.text_search``."""
    portal = await _resolve_portal(session, slug)
    stmt = select(Article).where(
        Article.portal_id == portal.id,
        Article.status == ARTICLE_STATUS_PUBLISHED,
    )
    if locale is not None:
        stmt = stmt.where(Article.locale == locale)
    if category_slug is not None:
        # Join to filter by category slug.
        stmt = stmt.join(
            Category, Category.id == Article.category_id
        ).where(Category.slug == category_slug)
    if query and query.strip():
        needle = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Article.title.ilike(needle),  # type: ignore[attr-defined]
                Article.description.ilike(needle),  # type: ignore[attr-defined]
                Article.content.ilike(needle),  # type: ignore[attr-defined]
            )
        )
    stmt = stmt.order_by(Article.position.asc(), Article.id.desc())  # type: ignore[attr-defined]
    rows = list((await session.exec(stmt)).all())
    return [present_article(a) for a in rows]


@public_router.get("/{slug}/articles/{article_slug}")
async def show_article(
    slug: Annotated[str, Path()],
    article_slug: Annotated[str, Path()],
    session: Annotated[AsyncSession, Depends(get_session)],
    locale: str | None = Query(None),
) -> dict[str, Any]:
    """``GET /hc/<slug>/articles/<article_slug>`` — single published article.

    404 when the portal is archived, the article is missing, or it is
    not published (drafts + archived articles never surface). When
    ``locale`` is supplied it scopes the lookup to that locale —
    Chatwoot allows the same article_slug in multiple locales.
    """
    portal = await _resolve_portal(session, slug)
    stmt = select(Article).where(
        Article.portal_id == portal.id,
        Article.slug == article_slug,
        Article.status == ARTICLE_STATUS_PUBLISHED,
    )
    if locale is not None:
        stmt = stmt.where(Article.locale == locale)
    article = (await session.exec(stmt)).first()
    if article is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return present_article(article)


@public_router.get("/{slug}/categories")
async def index_categories(
    slug: Annotated[str, Path()],
    session: Annotated[AsyncSession, Depends(get_session)],
    locale: str | None = Query(None),
) -> list[dict[str, Any]]:
    """Categories for a portal, optionally locale-filtered."""
    portal = await _resolve_portal(session, slug)
    stmt = select(Category).where(Category.portal_id == portal.id)
    if locale is not None:
        stmt = stmt.where(Category.locale == locale)
    stmt = stmt.order_by(Category.position.asc(), Category.id.asc())  # type: ignore[attr-defined]
    rows = list((await session.exec(stmt)).all())
    return [present_category(c) for c in rows]


__all__ = ["public_router"]
