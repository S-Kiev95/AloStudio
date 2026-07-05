"""Portal/Category/Article CRUD service.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/portals_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/articles_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/categories_controller.rb
  reference/chatwoot/app/models/portal.rb / article.rb / category.rb
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.portals.models import (
    Article,
    Category,
    Portal,
    article_status_from_str,
)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _slugify(raw: str | None) -> str:
    if not raw:
        return ""
    return re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")


def _validate_slug(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Slug can't be blank"}
        )
    slug = raw.strip()
    if not _SLUG_RE.match(slug):
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Slug is invalid"}
        )
    return slug


# ---------------------------------------------------------------------------
# Portal
# ---------------------------------------------------------------------------
async def list_portals(
    session: AsyncSession, *, account_id: int
) -> list[Portal]:
    return list(
        (
            await session.exec(
                select(Portal)
                .where(Portal.account_id == account_id)
                .order_by(Portal.id.asc())  # type: ignore[attr-defined]
            )
        ).all()
    )


async def fetch_portal_by_slug(
    session: AsyncSession, *, account_id: int, slug: str
) -> Portal | None:
    return (
        await session.exec(
            select(Portal).where(
                Portal.account_id == account_id, Portal.slug == slug
            )
        )
    ).first()


async def create_portal(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> Portal:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Name can't be blank"}
        )
    slug = _validate_slug(payload.get("slug") or _slugify(name))
    portal = Portal(
        account_id=account_id,
        name=name,
        slug=slug,
        custom_domain=payload.get("custom_domain"),
        color=payload.get("color"),
        homepage_link=payload.get("homepage_link"),
        page_title=payload.get("page_title"),
        header_text=payload.get("header_text"),
        logo=payload.get("logo"),
        config=payload.get("config") or {"allowed_locales": ["en"]},
    )
    session.add(portal)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Slug has already been taken"},
        ) from exc
    await session.refresh(portal)
    return portal


async def update_portal(
    session: AsyncSession, *, portal: Portal, payload: dict[str, Any]
) -> Portal:
    if "name" in payload:
        new_name = (payload.get("name") or "").strip()
        if not new_name:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "Name can't be blank"},
            )
        portal.name = new_name
    for key in (
        "custom_domain",
        "color",
        "homepage_link",
        "page_title",
        "header_text",
        "logo",
    ):
        if key in payload:
            # Empty string clears the field (logo maps back to NULL).
            value = payload.get(key)
            setattr(portal, key, value if value != "" or key != "logo" else None)
    if "config" in payload:
        config = payload.get("config")
        if config is not None and not isinstance(config, dict):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "Config must be an object"},
            )
        portal.config = config or {}
    if "archived" in payload:
        portal.archived = bool(payload.get("archived"))
    session.add(portal)
    await session.flush()
    await session.refresh(portal)
    return portal


async def destroy_portal(session: AsyncSession, *, portal: Portal) -> None:
    await session.delete(portal)
    await session.flush()


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
async def list_categories(
    session: AsyncSession,
    *,
    portal_id: int,
    locale: str | None = None,
) -> list[Category]:
    stmt = select(Category).where(Category.portal_id == portal_id)
    if locale is not None:
        stmt = stmt.where(Category.locale == locale)
    stmt = stmt.order_by(Category.id.asc())  # type: ignore[attr-defined]
    return list((await session.exec(stmt)).all())


async def fetch_category(
    session: AsyncSession, *, portal_id: int, category_id: int
) -> Category | None:
    return (
        await session.exec(
            select(Category).where(
                Category.id == category_id,
                Category.portal_id == portal_id,
            )
        )
    ).first()


async def create_category(
    session: AsyncSession,
    *,
    account_id: int,
    portal: Portal,
    payload: dict[str, Any],
) -> Category:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Name can't be blank"}
        )
    slug = _validate_slug(payload.get("slug") or _slugify(name))
    locale = payload.get("locale") or "en"
    cat = Category(
        account_id=account_id,
        portal_id=portal.id,
        name=name,
        description=payload.get("description"),
        position=payload.get("position"),
        locale=locale,
        slug=slug,
        parent_category_id=payload.get("parent_category_id"),
        associated_category_id=payload.get("associated_category_id"),
        icon=payload.get("icon") or "",
    )
    session.add(cat)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Slug has already been taken"},
        ) from exc
    await session.refresh(cat)
    return cat


async def update_category(
    session: AsyncSession, *, category: Category, payload: dict[str, Any]
) -> Category:
    for key in (
        "name",
        "description",
        "position",
        "locale",
        "icon",
        "parent_category_id",
        "associated_category_id",
    ):
        if key in payload:
            setattr(category, key, payload.get(key))
    session.add(category)
    await session.flush()
    await session.refresh(category)
    return category


async def destroy_category(
    session: AsyncSession, *, category: Category
) -> None:
    await session.delete(category)
    await session.flush()


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------
async def list_articles(
    session: AsyncSession,
    *,
    portal_id: int,
    locale: str | None = None,
    status: int | None = None,
    category_id: int | None = None,
    query: str | None = None,
) -> list[Article]:
    stmt = select(Article).where(Article.portal_id == portal_id)
    if locale is not None:
        stmt = stmt.where(Article.locale == locale)
    if status is not None:
        stmt = stmt.where(Article.status == status)
    if category_id is not None:
        stmt = stmt.where(Article.category_id == category_id)
    if query and query.strip():
        # ILIKE over title/description/content — mirrors Chatwoot's
        # Article.text_search (against title/description/content).
        needle = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Article.title.ilike(needle),  # type: ignore[attr-defined]
                Article.description.ilike(needle),  # type: ignore[attr-defined]
                Article.content.ilike(needle),  # type: ignore[attr-defined]
            )
        )
    stmt = stmt.order_by(Article.id.desc())  # type: ignore[attr-defined]
    return list((await session.exec(stmt)).all())


async def fetch_article(
    session: AsyncSession, *, portal_id: int, article_id: int
) -> Article | None:
    return (
        await session.exec(
            select(Article).where(
                Article.id == article_id,
                Article.portal_id == portal_id,
            )
        )
    ).first()


async def create_article(
    session: AsyncSession,
    *,
    account_id: int,
    portal: Portal,
    author_id: int | None,
    payload: dict[str, Any],
) -> Article:
    title = (payload.get("title") or "").strip()
    if not title:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Title can't be blank"}
        )
    slug = _validate_slug(payload.get("slug") or _slugify(title))
    status_int = (
        article_status_from_str(payload.get("status"))
        if isinstance(payload.get("status"), str)
        else 0
    )
    art = Article(
        account_id=account_id,
        portal_id=portal.id,
        category_id=payload.get("category_id"),
        title=title,
        description=payload.get("description"),
        content=payload.get("content"),
        status=status_int,
        author_id=author_id,
        slug=slug,
        locale=payload.get("locale") or "en",
        position=payload.get("position"),
        meta=payload.get("meta") or {},
    )
    session.add(art)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Slug has already been taken"},
        ) from exc
    await session.refresh(art)
    return art


async def update_article(
    session: AsyncSession, *, article: Article, payload: dict[str, Any]
) -> Article:
    for key in (
        "title",
        "description",
        "content",
        "category_id",
        "locale",
        "position",
        "meta",
    ):
        if key in payload:
            setattr(article, key, payload.get(key))
    if "status" in payload:
        raw = payload.get("status")
        if isinstance(raw, str):
            article.status = article_status_from_str(raw)
        elif isinstance(raw, int):
            article.status = raw
    session.add(article)
    await session.flush()
    await session.refresh(article)
    return article


async def destroy_article(session: AsyncSession, *, article: Article) -> None:
    await session.delete(article)
    await session.flush()


__all__ = [
    "create_article",
    "create_category",
    "create_portal",
    "destroy_article",
    "destroy_category",
    "destroy_portal",
    "fetch_article",
    "fetch_category",
    "fetch_portal_by_slug",
    "list_articles",
    "list_categories",
    "list_portals",
    "update_article",
    "update_category",
    "update_portal",
]
