"""Pydantic schemas for Campaign."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CampaignBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    description: str | None = None
    message: str | None = None
    inbox_id: int | None = None
    sender_id: int | None = None
    enabled: bool | None = None
    campaign_type: str | int | None = None
    scheduled_at: datetime | str | None = None
    audience: list[dict[str, Any]] | None = None
    trigger_rules: dict[str, Any] | None = None
    trigger_only_during_business_hours: bool | None = None
    template_params: dict[str, Any] | None = None


class CampaignEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    campaign: CampaignBody


__all__ = ["CampaignBody", "CampaignEnvelope"]
