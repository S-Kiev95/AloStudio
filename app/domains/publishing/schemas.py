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


class SignatureIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str = Field(min_length=1, max_length=2000)
    auto_add: bool = False


class SignatureUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str | None = Field(default=None, min_length=1, max_length=2000)
    auto_add: bool | None = None


class PublicationSetIn(BaseModel):
    """A saved composer: everything a publication takes but its date."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=120)
    content: str | None = None
    media: list[MediaItem] = Field(default_factory=list)
    targets: list[PublicationTargetIn] = Field(default_factory=list)


class PublicationSetUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = None
    media: list[MediaItem] | None = None
    targets: list[PublicationTargetIn] | None = None


class AutopostIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=120)
    feed_url: str = Field(min_length=1, max_length=2000)
    mode: str = "publish"
    active: bool = True
    start_with_latest: bool = False
    channel_ids: list[int] = Field(default_factory=list)


class AutopostUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    feed_url: str | None = Field(default=None, min_length=1, max_length=2000)
    mode: str | None = None
    active: bool | None = None
    start_with_latest: bool | None = None
    channel_ids: list[int] | None = None


class FeedPreviewIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    feed_url: str = Field(min_length=1, max_length=2000)


class ChannelConnectIn(BaseModel):
    """Values pasted to connect a network that connects by form."""

    model_config = ConfigDict(extra="ignore")

    fields: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "AutopostIn",
    "AutopostUpdate",
    "ChannelConnectIn",
    "FeedPreviewIn",
    "MediaItem",
    "PublicationCreate",
    "PublicationSetIn",
    "PublicationSetUpdate",
    "PublicationTargetIn",
    "PublicationUpdate",
    "SignatureIn",
    "SignatureUpdate",
]
