"""Portal / Article / Category HTTP endpoints.

Ports the dashboard-side CRUD from
``reference/chatwoot/app/controllers/api/v1/accounts/portals_controller.rb``
(+ nested articles + categories controllers).

Route map (admin-only):

  * ``GET    /api/v1/accounts/{id}/portals``
  * ``POST   /api/v1/accounts/{id}/portals``
  * ``GET    /api/v1/accounts/{id}/portals/{slug}``
  * ``PATCH  /api/v1/accounts/{id}/portals/{slug}``
  * ``DELETE /api/v1/accounts/{id}/portals/{slug}``
  * ``GET    /api/v1/accounts/{id}/portals/{slug}/categories``
  * ``POST   /api/v1/accounts/{id}/portals/{slug}/categories``
  * ``GET    /api/v1/accounts/{id}/portals/{slug}/categories/{cid}``
  * ``PATCH  /api/v1/accounts/{id}/portals/{slug}/categories/{cid}``
  * ``DELETE /api/v1/accounts/{id}/portals/{slug}/categories/{cid}``
  * ``GET    /api/v1/accounts/{id}/portals/{slug}/articles``
  * ``POST   /api/v1/accounts/{id}/portals/{slug}/articles``
  * ``GET    /api/v1/accounts/{id}/portals/{slug}/articles/{aid}``
  * ``PATCH  /api/v1/accounts/{id}/portals/{slug}/articles/{aid}``
  * ``DELETE /api/v1/accounts/{id}/portals/{slug}/articles/{aid}``

Deferred (Phase 9 follow-up):
  * Public Help Center surface (`/hc/<slug>`).
  * Logo upload + send_instructions email + archive action.
  * Article ``embeddings`` (pgvector — Phase 10).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.portals.models import (
    Portal,
    article_status_from_str,
)
from app.domains.portals.presenters import (
    present_article,
    present_category,
    present_portal,
)
from app.domains.portals.schemas import (
    ArticleEnvelope,
    CategoryEnvelope,
    PortalEnvelope,
)
from app.domains.portals.service import (
    create_article,
    create_category,
    create_portal,
    destroy_article,
    destroy_category,
    destroy_portal,
    fetch_article,
    fetch_category,
    fetch_portal_by_slug,
    list_articles,
    list_categories,
    list_portals,
    update_article,
    update_category,
    update_portal,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/portals",
    tags=["portals"],
)


async def _find_portal(
    session: AsyncSession, *, account_id: int, slug: str
) -> Portal:
    portal = await fetch_portal_by_slug(
        session, account_id=account_id, slug=slug
    )
    if portal is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return portal


# ===========================================================================
# Portal
# ===========================================================================
@router.get("")
async def index_portals(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await list_portals(session, account_id=ctx.account.id)
    return [present_portal(p) for p in rows]


@router.post("", status_code=status.HTTP_200_OK)
async def create_portal_endpoint(
    payload: PortalEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    body = payload.portal.model_dump(exclude_unset=True)
    portal = await create_portal(
        session, account_id=ctx.account.id, payload=body
    )
    return present_portal(portal)


@router.get("/{slug}")
async def show_portal(
    slug: Annotated[str, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    return present_portal(portal)


@router.patch("/{slug}")
async def update_portal_endpoint(
    slug: Annotated[str, Path()],
    payload: PortalEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    body = payload.portal.model_dump(exclude_unset=True)
    updated = await update_portal(
        session, portal=portal, payload=body
    )
    return present_portal(updated)


@router.delete("/{slug}", status_code=status.HTTP_200_OK)
async def destroy_portal_endpoint(
    slug: Annotated[str, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    await destroy_portal(session, portal=portal)
    return {}


# ===========================================================================
# Category
# ===========================================================================
@router.get("/{slug}/categories")
async def index_categories(
    slug: Annotated[str, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    locale: str | None = Query(None),
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    rows = await list_categories(
        session, portal_id=portal.id, locale=locale
    )
    return [present_category(c) for c in rows]


@router.post("/{slug}/categories", status_code=status.HTTP_200_OK)
async def create_category_endpoint(
    slug: Annotated[str, Path()],
    payload: CategoryEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    body = payload.category.model_dump(exclude_unset=True)
    cat = await create_category(
        session,
        account_id=ctx.account.id,
        portal=portal,
        payload=body,
    )
    return present_category(cat)


@router.patch("/{slug}/categories/{category_id}")
async def update_category_endpoint(
    slug: Annotated[str, Path()],
    category_id: Annotated[int, Path()],
    payload: CategoryEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    cat = await fetch_category(
        session, portal_id=portal.id, category_id=category_id
    )
    if cat is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    body = payload.category.model_dump(exclude_unset=True)
    updated = await update_category(
        session, category=cat, payload=body
    )
    return present_category(updated)


@router.delete(
    "/{slug}/categories/{category_id}", status_code=status.HTTP_200_OK
)
async def destroy_category_endpoint(
    slug: Annotated[str, Path()],
    category_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    cat = await fetch_category(
        session, portal_id=portal.id, category_id=category_id
    )
    if cat is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    await destroy_category(session, category=cat)
    return {}


# ===========================================================================
# Article
# ===========================================================================
@router.get("/{slug}/articles")
async def index_articles(
    slug: Annotated[str, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    locale: str | None = Query(None),
    status: str | None = Query(None),
    category_id: int | None = Query(None),
    query: str | None = Query(None),
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    status_int: int | None = None
    if status is not None:
        try:
            status_int = article_status_from_str(status)
        except ValueError as exc:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "status is invalid"},
            ) from exc
    rows = await list_articles(
        session,
        portal_id=portal.id,
        locale=locale,
        status=status_int,
        category_id=category_id,
        query=query,
    )
    return [present_article(a) for a in rows]


@router.post("/{slug}/articles", status_code=status.HTTP_200_OK)
async def create_article_endpoint(
    slug: Annotated[str, Path()],
    payload: ArticleEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    body = payload.article.model_dump(exclude_unset=True)
    art = await create_article(
        session,
        account_id=ctx.account.id,
        portal=portal,
        author_id=ctx.user.id,
        payload=body,
    )
    return present_article(art)


@router.get("/{slug}/articles/{article_id}")
async def show_article(
    slug: Annotated[str, Path()],
    article_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    art = await fetch_article(
        session, portal_id=portal.id, article_id=article_id
    )
    if art is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return present_article(art)


@router.patch("/{slug}/articles/{article_id}")
async def update_article_endpoint(
    slug: Annotated[str, Path()],
    article_id: Annotated[int, Path()],
    payload: ArticleEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    art = await fetch_article(
        session, portal_id=portal.id, article_id=article_id
    )
    if art is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    body = payload.article.model_dump(exclude_unset=True)
    updated = await update_article(
        session, article=art, payload=body
    )
    return present_article(updated)


@router.delete(
    "/{slug}/articles/{article_id}", status_code=status.HTTP_200_OK
)
async def destroy_article_endpoint(
    slug: Annotated[str, Path()],
    article_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    portal = await _find_portal(
        session, account_id=ctx.account.id, slug=slug
    )
    art = await fetch_article(
        session, portal_id=portal.id, article_id=article_id
    )
    if art is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    await destroy_article(session, article=art)
    return {}


__all__ = ["router"]
