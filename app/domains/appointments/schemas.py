"""Pydantic schemas for the appointments endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contact_id: int
    product_id: int | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    status: str = "scheduled"
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contact_id: int | None = None
    product_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str | None = None
    notes: str | None = None


__all__ = ["AppointmentCreate", "AppointmentUpdate"]
