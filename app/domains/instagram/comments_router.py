"""Instagram comment moderation HTTP endpoints (I.7).

Admin-only surface for reading + moderating comments on owned media.
Listing/creating is anchored under the post (which carries the
``ig_media_id``); per-comment actions (reply / hide / delete) address
the local ``instagram_comments`` row by its id.

Route map (admin-only):

  * ``GET    /api/v1/accounts/{id}/instagram_posts/{post_id}/comments``
  * ``POST   /api/v1/accounts/{id}/instagram_posts/{post_id}/comments``
  * ``POST   /api/v1/accounts/{id}/instagram_comments/{comment_id}/replies``
  * ``POST   /api/v1/accounts/{id}/instagram_comments/{comment_id}/hide``
  * ``DELETE /api/v1/accounts/{id}/instagram_comments/{comment_id}``

A single router with absolute paths (no prefix) keeps both the
post-nested and comment-addressed routes in one place.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import InstagramChannel
from app.domains.instagram import publishing_service as svc
from app.domains.instagram.presenters import present_comment
from app.domains.instagram.schemas import (
    InstagramCommentCreate,
    InstagramCommentHide,
)

router = APIRouter(tags=["instagram-comments"])

_POSTS = "/api/v1/accounts/{account_id}/instagram_posts/{post_id}/comments"
_COMMENTS = "/api/v1/accounts/{account_id}/instagram_comments/{comment_id}"


async def _published_post_or_404(session, *, account_id, post_id):
    """Resolve a post that has an ``ig_media_id`` (i.e. has been
    published, so it can carry comments). 404 if missing; 422 if it
    has nothing on Meta yet."""
    post = await svc.get_post(
        session, account_id=account_id, post_id=post_id
    )
    if post is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    if not post.ig_media_id:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "post has no published media yet"},
        )
    return post


async def _channel_or_422(session, channel_instagram_id: int):
    channel = await session.get(InstagramChannel, channel_instagram_id)
    if channel is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "instagram channel row not found"},
        )
    return channel


async def _comment_or_404(session, *, account_id, comment_id):
    comment = await svc.get_comment(
        session, account_id=account_id, comment_id=comment_id
    )
    if comment is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return comment


@router.get(_POSTS)
async def index_comments(
    post_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    """Live-fetch comments for the post's media from Meta, upsert the
    local mirror, and return the stored rows (hidden included)."""
    assert ctx.account.id is not None
    post = await _published_post_or_404(
        session, account_id=ctx.account.id, post_id=post_id
    )
    channel = await _channel_or_422(session, post.channel_instagram_id)
    rows = await svc.list_comments_on_meta(
        session,
        channel=channel,
        account_id=ctx.account.id,
        ig_media_id=post.ig_media_id,
    )
    return [present_comment(c) for c in rows]


@router.post(_POSTS, status_code=status.HTTP_200_OK)
async def create_comment_endpoint(
    post_id: Annotated[int, Path()],
    payload: InstagramCommentCreate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    post = await _published_post_or_404(
        session, account_id=ctx.account.id, post_id=post_id
    )
    channel = await _channel_or_422(session, post.channel_instagram_id)
    comment = await svc.post_comment_on_meta(
        session,
        channel=channel,
        account_id=ctx.account.id,
        ig_media_id=post.ig_media_id,
        message=payload.message,
    )
    return present_comment(comment)


@router.post(
    f"{_COMMENTS}/replies", status_code=status.HTTP_200_OK
)
async def reply_comment_endpoint(
    comment_id: Annotated[int, Path()],
    payload: InstagramCommentCreate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    parent = await _comment_or_404(
        session, account_id=ctx.account.id, comment_id=comment_id
    )
    channel = await _channel_or_422(session, parent.channel_instagram_id)
    reply = await svc.reply_comment_on_meta(
        session,
        channel=channel,
        account_id=ctx.account.id,
        parent_comment=parent,
        message=payload.message,
    )
    return present_comment(reply)


@router.post(f"{_COMMENTS}/hide", status_code=status.HTTP_200_OK)
async def hide_comment_endpoint(
    comment_id: Annotated[int, Path()],
    payload: InstagramCommentHide,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    comment = await _comment_or_404(
        session, account_id=ctx.account.id, comment_id=comment_id
    )
    channel = await _channel_or_422(session, comment.channel_instagram_id)
    updated = await svc.hide_comment_on_meta(
        session, channel=channel, comment=comment, hide=payload.hide
    )
    return present_comment(updated)


@router.delete(_COMMENTS, status_code=status.HTTP_200_OK)
async def delete_comment_endpoint(
    comment_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    comment = await _comment_or_404(
        session, account_id=ctx.account.id, comment_id=comment_id
    )
    channel = await _channel_or_422(session, comment.channel_instagram_id)
    await svc.delete_comment_on_meta(
        session, channel=channel, comment=comment
    )
    return {"success": True}


__all__ = ["router"]
