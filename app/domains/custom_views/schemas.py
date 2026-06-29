"""Pydantic schemas for the custom_views (``custom_filters``) surface.

The frontend may send ``filter_type`` either as the enum string
("conversation"/"contact") or the raw int — both are accepted and
coerced in the router.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class CustomViewCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    filter_type: str | int | None = None
    query: dict[str, Any] = {}


class CustomViewUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    query: dict[str, Any] | None = None


__all__ = ["CustomViewCreate", "CustomViewUpdate"]
