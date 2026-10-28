"""Publications HTTP endpoints (admin OR agent read; admin-only writes,
like Instagram publishing — posting goes out under the brand).

Route map:
  * ``GET    /api/v1/accounts/{account_id}/publications/channels``
  * ``GET    /api/v1/accounts/{account_id}/publications/analytics``
  * ``GET    /api/v1/accounts/{account_id}/publications``
  * ``POST   /api/v1/accounts/{account_id}/publications``
  * ``GET    /api/v1/accounts/{account_id}/publications/{publication_id}``
  * ``PATCH  /api/v1/accounts/{account_id}/publications/{publication_id}``
  * ``DELETE /api/v1/accounts/{account_id}/publications/{publication_id}``
  * ``POST   /api/v1/accounts/{account_id}/publications/{publication_id}/retry``
  * ``POST   /api/v1/accounts/{account_id}/publications/{publication_id}/refresh_metrics``

A publication without a date (or due now) is claimed and enqueued right
away; a future one waits for the scheduler tick.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.publishing import analytics
from app.domains.publishing import service as svc
from app.domains.publishing.models import (
    PUBLICATION_STATE_PUBLISHING,
    PUBLICATION_STATE_SCHEDULED,
    Publication,
)
from app.domains.publishing.presenters import (
    present_channel,
    present_one_publication,
    present_publications,
)
from app.domains.publishing.schemas import PublicationCreate, PublicationUpdate

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/publications",
    tags=["publications"],
)


async def _find_publication(
    session: AsyncSession,
    ctx: AccountContext,
    publication_id: int,
    *,
    for_update: bool = False,
) -> Publication:
    assert ctx.account.id is not None
    row = await svc.get_publication(
        session,
        account_id=ctx.account.id,
        publication_id=publication_id,
        for_update=for_update,
    )
    if row is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return row


async def _publish_now_if_due(
    session: AsyncSession, publication: Publication
) -> None:
    """Enqueue a publication that should go out now — one scheduled for
    now or earlier (claimed first), or one put back to publishing by a
    retry. Commits first so the worker's own session sees it."""
    from app.workers.publishing import enqueue_publication

    if publication.state == PUBLICATION_STATE_SCHEDULED:
        due = (
            publication.scheduled_for is not None
            and publication.scheduled_for <= datetime.now(UTC)
        )
        if not due or not await svc.start_publishing(
            session, publication_id=publication.id  # type: ignore[arg-type]
        ):
            return
    elif publication.state != PUBLICATION_STATE_PUBLISHING:
        return
    await session.commit()
    await enqueue_publication(publication.id)  # type: ignore[arg-type]
    await session.refresh(publication)


@router.get("/channels")
async def index_channels(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    channels = await svc.list_channels(session, account_id=ctx.account.id)
    return [present_channel(inbox, network) for inbox, network in channels]


@router.get("/analytics")
async def publications_analytics(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    inbox_id: int | None = None,
) -> dict[str, Any]:
    """Defaults to the last 30 days."""
    assert ctx.account.id is not None
    until = _aware(to) or datetime.now(UTC)
    since = _aware(from_) or until - timedelta(days=30)
    return await analytics.analytics_summary(
        session,
        account_id=ctx.account.id,
        starts_from=since,
        starts_to=until,
        inbox_id=inbox_id,
    )

@router.get("")
async def index_publications(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    state: str | None = None,
    inbox_id: int | None = None,
    page: int = 1,
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await svc.list_publications(
        session,
        account_id=ctx.account.id,
        starts_from=from_,
        starts_to=to,
        state=state,
        inbox_id=inbox_id,
        page=page,
    )
    return await present_publications(session, rows)


@router.post("", status_code=status.HTTP_200_OK)
async def create_publication_endpoint(
    payload: PublicationCreate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    row = await svc.create_publication(
        session,
        account_id=ctx.account.id,
        payload=payload.model_dump(exclude_unset=True),
        created_by_id=ctx.user.id,
    )
    await _publish_now_if_due(session, row)
    return await present_one_publication(session, row)


@router.get("/{publication_id}")
async def show_publication(
    publication_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_publication(session, ctx, publication_id)
    return await present_one_publication(session, row)


@router.patch("/{publication_id}")
async def update_publication_endpoint(
    publication_id: Annotated[int, Path()],
    payload: PublicationUpdate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_publication(session, ctx, publication_id, for_update=True)
    updated = await svc.update_publication(
        session,
        publication=row,
        payload=payload.model_dump(exclude_unset=True),
    )
    await _publish_now_if_due(session, updated)
    return await present_one_publication(session, updated)


@router.delete("/{publication_id}", status_code=status.HTTP_200_OK)
async def delete_publication_endpoint(
    publication_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_publication(session, ctx, publication_id, for_update=True)
    await svc.delete_publication(session, publication=row)
    return {}


@router.post("/{publication_id}/retry", status_code=status.HTTP_200_OK)
async def retry_publication_endpoint(
    publication_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_publication(session, ctx, publication_id, for_update=True)
    updated = await svc.retry_publication(session, publication=row)
    await _publish_now_if_due(session, updated)
    return await present_one_publication(session, updated)


@router.post("/{publication_id}/refresh_metrics", status_code=status.HTTP_200_OK)
async def refresh_publication_metrics_endpoint(
    publication_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Read the figures of every published channel now, instead of waiting
    for the hourly refresh."""
    row = await _find_publication(session, ctx, publication_id)
    await analytics.refresh_publication_metrics(session, publication=row)
    return await present_one_publication(session, row)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


__all__ = ["router"]
