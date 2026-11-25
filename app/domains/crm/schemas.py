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
    value: float | str | None = None
    currency: str | None = Field(default=None, max_length=8)
    stage_id: int | None = None
    contact_id: int | None = None
    product_id: int | None = None
    owner_id: int | None = None
    conversation_id: int | None = None
    expected_close_on: str | None = None
    lost_reason: str | None = None
    position: float | None = None
    # Explicit decision when editing a won sale that already has allocated payments:
    # release_allocations=True turns existing allocations into client credit balance;
    # keep_allocations=True keeps them when only value increased and no installments exist.
    release_allocations: bool | None = None
    keep_allocations: bool | None = None


class InstallmentGenerateBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    count: int
    first_due_on: str
    frequency: str = "monthly"
    interval_days: int | None = None


class InstallmentItemBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    due_on: str
    amount: float | str


class OpportunityBillingBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    payment_terms: str | None = None
    due_on: str | None = None
    generate: InstallmentGenerateBody | None = None
    installments: list[InstallmentItemBody] | None = None
    # Convenience for "cash" sales: optionally create the full payment in one step.
    register_payment: bool = False
    payment_method: str | None = None
    paid_on: str | None = None
    payment_note: str | None = None


class InstallmentPatchBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    due_on: str | None = None
    amount: float | str | None = None


class PaymentAllocationInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    opportunity_id: int
    installment_id: int | None = None
    amount: float | str


class PaymentBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contact_id: int | None = None
    amount: float | str | None = None
    currency: str | None = Field(default=None, max_length=8)
    paid_on: str | None = None
    method: str | None = None
    note: str | None = None
    allocation_mode: str | None = None
    allocations: list[PaymentAllocationInput] | None = None


class PaymentPreviewBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contact_id: int
    amount: float | str
    currency: str | None = Field(default=None, max_length=8)
    allocation_mode: str = "auto"
    allocations: list[PaymentAllocationInput] | None = None
    exclude_payment_id: int | None = None
    as_of: str | None = None


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
    "ContactOriginBody",
    "InstallmentGenerateBody",
    "InstallmentItemBody",
    "InstallmentPatchBody",
    "MetaCatalogBody",
    "OpportunityBillingBody",
    "OpportunityBody",
    "PaymentAllocationInput",
    "PaymentBody",
    "PaymentPreviewBody",
    "PipelineBody",
]


class MetaCatalogBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    catalog_id: str = Field(min_length=1, max_length=40)
    # Left out to keep the stored one (changing only the catalogue).
    access_token: str | None = Field(default=None, max_length=1000)
