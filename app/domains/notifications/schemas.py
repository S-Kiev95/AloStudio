"""Pydantic schemas for the notifications surface."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NotificationSettingsUpdate(BaseModel):
    """``PATCH /notification_settings`` — both arrays optional."""

    model_config = ConfigDict(extra="ignore")

    selected_email_flags: list[str] | None = None
    selected_push_flags: list[str] | None = None


__all__ = ["NotificationSettingsUpdate"]
