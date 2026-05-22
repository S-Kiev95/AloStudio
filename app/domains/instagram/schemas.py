"""Pydantic schemas for the Instagram publishing endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InstagramPostCreate(BaseModel):
    """Body for ``POST /api/v1/accounts/{id}/instagram_posts``.

    ``inbox_id`` selects which Instagram channel publishes. ``source``
    shape depends on ``media_type`` (validated server-side):
      * IMAGE:    ``{"image_url": "..."}``
      * VIDEO:    ``{"video_url": "...", "thumb_offset": 1000}``
      * REELS:    ``{"video_url": "...", "cover_url": "...",
                     "share_to_feed": true}``
      * CAROUSEL: ``{"children": [{"image_url": "..."}, ...]}``
      * STORIES:  ``{"image_url": "..."}`` or ``{"video_url": "..."}``

    ``scheduled_for`` null → publish immediately; future → queued;
    past → 422.
    """

    model_config = ConfigDict(extra="ignore")

    inbox_id: int
    media_type: Literal["IMAGE", "VIDEO", "REELS", "CAROUSEL", "STORIES"]
    source: dict[str, Any]
    caption: str | None = None
    scheduled_for: datetime | None = None
    # I.11 — optionally link the post/story to catalogue products so an AI
    # agent has product context when an IG user comments/DMs about it.
    product_ids: list[int] | None = None


class InstagramCommentCreate(BaseModel):
    """Body for posting a comment on a media or replying to a comment."""

    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, max_length=2200)


class InstagramCommentHide(BaseModel):
    """Body for the hide/unhide moderation action."""

    model_config = ConfigDict(extra="ignore")

    hide: bool = True


class InstagramManualConnect(BaseModel):
    """Body for the advanced/manual connect — paste a token (e.g. a
    permanent System User token) to create an Instagram inbox+channel.

    ``login_type`` decides capabilities: ``facebook`` enables DELETE
    media; ``instagram`` (Instagram Login) does not.
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=255)
    instagram_id: str = Field(min_length=1)
    access_token: str = Field(min_length=1)
    login_type: Literal["facebook", "instagram"] = "facebook"
    expires_at: datetime | None = None


__all__ = [
    "InstagramCommentCreate",
    "InstagramCommentHide",
    "InstagramManualConnect",
    "InstagramPostCreate",
]
