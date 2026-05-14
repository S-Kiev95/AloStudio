"""Pydantic schemas for Integration hooks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class HookBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app_id: str | None = None
    inbox_id: int | None = None
    hook_type: str | None = None
    settings: dict[str, Any] | None = None
    status: Any | None = None


class HookEnvelope(BaseModel):
    """Top-level wrapper — mirrors ``params.require(:hook)``."""

    model_config = ConfigDict(extra="ignore")

    hook: HookBody


__all__ = ["HookBody", "HookEnvelope"]
