"""Pydantic schemas for the product catalogue endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    sku: str | None = None
    price: float | None = None
    currency: str | None = Field(default=None, max_length=8)
    url: str | None = None
    image_url: str | None = None
    enabled: bool = True


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    sku: str | None = None
    price: float | None = None
    currency: str | None = Field(default=None, max_length=8)
    url: str | None = None
    image_url: str | None = None
    enabled: bool | None = None


__all__ = ["ProductCreate", "ProductUpdate"]
