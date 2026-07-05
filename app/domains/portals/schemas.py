"""Pydantic schemas for Portal / Category / Article."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class PortalBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    slug: str | None = None
    custom_domain: str | None = None
    color: str | None = None
    homepage_link: str | None = None
    page_title: str | None = None
    header_text: str | None = None
    logo: str | None = None
    config: dict[str, Any] | None = None
    archived: bool | None = None


class PortalEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    portal: PortalBody


class CategoryBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    position: int | None = None
    locale: str | None = None
    parent_category_id: int | None = None
    associated_category_id: int | None = None
    icon: str | None = None


class CategoryEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: CategoryBody


class ArticleBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    slug: str | None = None
    description: str | None = None
    content: str | None = None
    category_id: int | None = None
    locale: str | None = None
    position: int | None = None
    meta: dict[str, Any] | None = None
    status: str | int | None = None


class ArticleEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    article: ArticleBody


__all__ = [
    "ArticleBody",
    "ArticleEnvelope",
    "CategoryBody",
    "CategoryEnvelope",
    "PortalBody",
    "PortalEnvelope",
]
