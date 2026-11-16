"""Request bodies for the sales pipeline endpoints. Validation of what
depends on the account (stages, contacts, owners) lives in the service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PipelineBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, max_length=255)
    rotten_days: int | None = None
    stages: list[dict[str, Any]] | None = None


class OpportunityBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    description: str | None = None
    value: float | None = None
    currency: str | None = Field(default=None, max_length=8)
    stage_id: int | None = None
    contact_id: int | None = None
    product_id: int | None = None
    owner_id: int | None = None
    conversation_id: int | None = None
    expected_close_on: str | None = None
    lost_reason: str | None = None
    position: float | None = None




class ActivityBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str | None = None
    title: str | None = None
    description: str | None = None
    due_at: str | None = None
    owner_id: int | None = None
    contact_id: int | None = None
    opportunity_id: int | None = None
    done: bool | None = None


class CompanyBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    tax_id: str | None = Field(default=None, max_length=64)
    notes: str | None = None


class CompanyContactBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contact_id: int


class ContactOriginBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str | None = None
    channel: str | None = None
    detail: str | None = Field(default=None, max_length=255)


__all__ = [
    "ActivityBody",
    "CompanyBody",
    "CompanyContactBody",
    "OpportunityBody",
    "PipelineBody",
]


class MetaCatalogBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    catalog_id: str = Field(min_length=1, max_length=40)
    # Left out to keep the stored one (changing only the catalogue).
    access_token: str | None = Field(default=None, max_length=1000)
