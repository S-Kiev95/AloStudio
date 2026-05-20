"""Instagram publishing HTTP endpoints.

Dashboard-facing CRUD for scheduled / immediate Instagram posts.
Distinct from Phase 5e's ``router.py`` (which handles the inbound
DM webhook).

Route map (admin-only):

  * ``GET  /api/v1/accounts/{id}/instagram_posts``
  * ``POST /api/v1/accounts/{id}/instagram_posts``
  * ``GET  /api/v1/accounts/{id}/instagram_posts/{post_id}``

Scheduling semantics (per the user's I.2 decision):
  * ``scheduled_for=null`` → enqueue ARQ task immediately
  * future → row stays ``pending``; the 5-min scheduler fires it
  * past → 422
  * no upper-bound cap on how far ahead you can schedule
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import (
    CHANNEL_TYPE_INSTAGRAM,
    Inbox,
)
from app.domains.instagram import publishing_service as svc
from app.domains.instagram.presenters import present_post
from app.domains.instagram.schemas import InstagramPostCreate

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/instagram_posts",
    tags=["instagram-publishing"],
)


async def _resolve_channel_id(
    session: AsyncSession, *, account_id: int, inbox_id: int
) -> int:
    """Map an inbox to its ``channel_instagram`` id, validating the
    inbox is an Instagram inbox on this account."""
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.id == inbox_id, Inbox.account_id == account_id
            )
        )
    ).first()
    if inbox is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    if inbox.channel_type != CHANNEL_TYPE_INSTAGRAM:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "inbox is not an Instagram inbox"},
        )
    return inbox.channel_id


@router.get("")
async def index_posts(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    state: str | None = None,
    page: int = 1,
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await svc.list_posts(
        session, account_id=ctx.account.id, state=state, page=page
    )
    return [present_post(p) for p in rows]


@router.post("", status_code=status.HTTP_200_OK)
async def create_post_endpoint(
    payload: InstagramPostCreate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Create a publish request.

    Validates ``scheduled_for`` (must be in the future if present),
    persists the post, and either enqueues immediately or leaves it
    for the scheduler.
    """
    assert ctx.account.id is not None

    # Reject past scheduled times. No upper bound — user can schedule
    # arbitrarily far ahead (design decision).
    scheduled_for = payload.scheduled_for
    if scheduled_for is not None:
        now = datetime.now(UTC)
        # Normalise naive datetimes to UTC for the comparison.
        cmp = (
            scheduled_for
            if scheduled_for.tzinfo is not None
            else scheduled_for.replace(tzinfo=UTC)
        )
        if cmp <= now:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "scheduled_for must be in the future"
                },
            )

    channel_id = await _resolve_channel_id(
        session, account_id=ctx.account.id, inbox_id=payload.inbox_id
    )
    post = await svc.create_post(
        session,
        account_id=ctx.account.id,
        inbox_id=payload.inbox_id,
        channel_instagram_id=channel_id,
        media_type=payload.media_type,
        source=payload.source,
        caption=payload.caption,
        scheduled_for=scheduled_for,
    )

    # Immediate publish → enqueue now. Scheduled → the 5-min
    # scheduler picks it up at fire time.
    if scheduled_for is None:
        # Commit first so the worker's separate session sees the row.
        await session.commit()
        from app.workers.instagram import enqueue_publish

        await enqueue_publish(post.id)
        # Re-read the (possibly already-published in inline-fallback)
        # row for the response.
        await session.refresh(post)

    return present_post(post)


@router.get("/{post_id}")
async def show_post(
    post_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    post = await svc.get_post(
        session, account_id=ctx.account.id, post_id=post_id
    )
    if post is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    containers = await svc.list_containers(session, post_id=post.id)
    return present_post(post, containers=containers)


@router.delete("/{post_id}")
async def delete_post_endpoint(
    post_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Delete a published post on Instagram + flip the row to
    ``deleted``. Only ``published`` posts can be removed on Meta (other
    states 422). Meta-side restrictions (carousel children, ad-promoted
    posts, live video) surface as a 422 with the Meta error code.
    """
    assert ctx.account.id is not None
    post = await svc.delete_media_on_meta(
        session, account_id=ctx.account.id, post_id=post_id
    )
    return present_post(post)


__all__ = ["router"]
