"""Pydantic schemas for the publications endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MediaItem(BaseModel):
    """A library asset (``media_id``) or an external file (``type`` + ``url``)."""

    model_config = ConfigDict(extra="ignore")

    media_id: int | None = None
    type: str | None = None
    url: str | None = None


class PublicationTargetIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_id: int
    settings: dict[str, Any] = Field(default_factory=dict)
    content_override: str | None = None


class PublicationCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str | None = None
    media: list[MediaItem] = Field(default_factory=list)
    scheduled_for: datetime | None = None
    # A draft is saved but never published, even with a date, until it is
    # saved again with ``draft: false``.
    draft: bool = False
    targets: list[PublicationTargetIn] = Field(min_length=1)


class PublicationUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str | None = None
    media: list[MediaItem] | None = None
    scheduled_for: datetime | None = None
    draft: bool | None = None
    targets: list[PublicationTargetIn] | None = Field(default=None, min_length=1)


class ChannelConnectIn(BaseModel):
    """Values pasted to connect a network that connects by form."""

    model_config = ConfigDict(extra="ignore")

    fields: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "ChannelConnectIn",
    "MediaItem",
    "PublicationCreate",
    "PublicationTargetIn",
    "PublicationUpdate",
]
