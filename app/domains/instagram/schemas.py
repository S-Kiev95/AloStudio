"""Pydantic schemas for the Instagram publishing endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


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


__all__ = ["InstagramPostCreate"]
