"""Wire-shape presenters for Instagram publishing."""

from __future__ import annotations

from typing import Any

from app.domains.instagram.models import (
    InstagramComment,
    InstagramPost,
    InstagramPostContainer,
)


def present_post(
    post: InstagramPost,
    *,
    containers: list[InstagramPostContainer] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": post.id,
        "account_id": post.account_id,
        "inbox_id": post.inbox_id,
        "channel_instagram_id": post.channel_instagram_id,
        "state": post.state,
        "media_type": post.media_type,
        "caption": post.caption,
        "source": post.source or {},
        "ig_media_id": post.ig_media_id,
        "ig_permalink": post.ig_permalink,
        "error_code": post.error_code,
        "error_message": post.error_message,
        "scheduled_for": (
            post.scheduled_for.isoformat() if post.scheduled_for else None
        ),
        "published_at": (
            post.published_at.isoformat() if post.published_at else None
        ),
        "created_at": (
            int(post.created_at.timestamp()) if post.created_at else None
        ),
    }
    if containers is not None:
        body["containers"] = [
            {
                "id": c.id,
                "ig_container_id": c.ig_container_id,
                "position": c.position,
                "status_code": c.status_code,
                "poll_count": c.poll_count,
            }
            for c in containers
        ]
    return body


def present_comment(comment: InstagramComment) -> dict[str, Any]:
    return {
        "id": comment.id,
        "account_id": comment.account_id,
        "channel_instagram_id": comment.channel_instagram_id,
        "ig_comment_id": comment.ig_comment_id,
        "ig_media_id": comment.ig_media_id,
        "parent_comment_id": comment.parent_comment_id,
        "from_username": comment.from_username,
        "from_id": comment.from_id,
        "text": comment.text,
        "hidden": comment.hidden,
        "conversation_id": comment.conversation_id,
        "ig_created_at": (
            comment.ig_created_at.isoformat()
            if comment.ig_created_at
            else None
        ),
    }


__all__ = ["present_comment", "present_post"]
