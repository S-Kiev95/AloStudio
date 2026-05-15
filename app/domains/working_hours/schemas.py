"""Pydantic schemas for WorkingHour."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WorkingHourBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    day_of_week: int | None = None
    closed_all_day: bool | None = None
    open_all_day: bool | None = None
    open_hour: int | None = None
    open_minutes: int | None = None
    close_hour: int | None = None
    close_minutes: int | None = None


class WorkingHourEnvelope(BaseModel):
    """``params.require(:working_hour)``."""

    model_config = ConfigDict(extra="ignore")

    working_hour: WorkingHourBody


__all__ = ["WorkingHourBody", "WorkingHourEnvelope"]
