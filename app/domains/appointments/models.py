"""Appointment model (account-scoped CRM agenda)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

APPOINTMENT_STATUS_SCHEDULED = "scheduled"
APPOINTMENT_STATUS_CONFIRMED = "confirmed"
APPOINTMENT_STATUS_CANCELLED = "cancelled"
APPOINTMENT_STATUS_DONE = "done"

APPOINTMENT_STATUSES: tuple[str, ...] = (
    APPOINTMENT_STATUS_SCHEDULED,
    APPOINTMENT_STATUS_CONFIRMED,
    APPOINTMENT_STATUS_CANCELLED,
    APPOINTMENT_STATUS_DONE,
)

AppointmentStatus = Literal["scheduled", "confirmed", "cancelled", "done"]


class Appointment(TimestampMixin, table=True):
    """A scheduled appointment linked to a contact and an optional product."""

    __tablename__ = "appointments"
    __table_args__ = (
        Index("index_appointments_on_account_id", "account_id"),
        Index("index_appointments_on_contact_id", "contact_id"),
        Index(
            "index_appointments_on_account_id_and_starts_at",
            "account_id",
            "starts_at",
        ),
        Index("ix_appointments_product_id", "product_id"),
        Index("ix_appointments_created_by_id", "created_by_id"),
        UniqueConstraint(
            "account_id",
            "external_id",
            name="uniq_appointments_account_external_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    contact_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    product_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    title: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    starts_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    ends_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    status: str = Field(
        default=APPOINTMENT_STATUS_SCHEDULED,
        sa_column=Column(
            String, nullable=False, server_default=APPOINTMENT_STATUS_SCHEDULED
        ),
    )
    notes: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    external_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )


__all__ = [
    "APPOINTMENT_STATUSES",
    "APPOINTMENT_STATUS_CANCELLED",
    "APPOINTMENT_STATUS_CONFIRMED",
    "APPOINTMENT_STATUS_DONE",
    "APPOINTMENT_STATUS_SCHEDULED",
    "Appointment",
    "AppointmentStatus",
]
