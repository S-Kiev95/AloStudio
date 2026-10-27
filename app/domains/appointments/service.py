"""Appointments service — account-scoped CRUD and domain validations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import lazyload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.appointments.models import (
    APPOINTMENT_STATUS_SCHEDULED,
    APPOINTMENT_STATUSES,
    Appointment,
)
from app.domains.contacts.models import Contact
from app.domains.conversations.events import (
    APPOINTMENT_CREATED,
    APPOINTMENT_UPDATED,
    dispatcher,
)
from app.domains.products.models import Product

# Attributes whose change makes an ``appointment.updated`` event.
_EVENT_ATTRIBUTES = (
    "contact_id",
    "product_id",
    "title",
    "description",
    "starts_at",
    "ends_at",
    "status",
    "notes",
)


def _validate_title(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "title is required"},
        )
    if len(raw) > 255:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "title exceeds 255 chars"},
        )
    return raw


def _validate_status(raw: Any) -> str:
    if not isinstance(raw, str) or raw not in APPOINTMENT_STATUSES:
        allowed = ", ".join(APPOINTMENT_STATUSES)
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"status must be one of: {allowed}"},
        )
    return raw


def _coerce_datetime(raw: Any, *, field_name: str) -> datetime:
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": f"{field_name} must be a valid ISO 8601 datetime"
                },
            ) from exc
    else:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": f"{field_name} must be a valid ISO 8601 datetime"
            },
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _validate_time_range(
    starts_at: datetime, ends_at: datetime | None
) -> None:
    if ends_at is not None and ends_at < starts_at:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "ends_at must be greater than or equal to starts_at"
            },
        )


async def _ensure_contact_in_account(
    session: AsyncSession, *, account_id: int, contact_id: Any
) -> Contact:
    if not isinstance(contact_id, int) or isinstance(contact_id, bool):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "contact_id is required"},
        )
    contact = (
        await session.exec(
            select(Contact)
            .where(
                Contact.id == contact_id,
                Contact.account_id == account_id,
            )
            .options(lazyload("*"))
        )
    ).first()
    if contact is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "El contacto no existe o no pertenece a esta cuenta"
            },
        )
    return contact


async def _ensure_product_in_account(
    session: AsyncSession, *, account_id: int, product_id: Any
) -> Product:
    if not isinstance(product_id, int) or isinstance(product_id, bool):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "product_id is invalid"},
        )
    product = (
        await session.exec(
            select(Product).where(
                Product.id == product_id,
                Product.account_id == account_id,
            )
        )
    ).first()
    if product is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "El producto no existe o no pertenece a esta cuenta"
            },
        )
    return product


async def create_appointment(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
    created_by_id: int | None = None,
    emit_event: bool = True,
) -> Appointment:
    title = _validate_title(payload.get("title"))
    await _ensure_contact_in_account(
        session, account_id=account_id, contact_id=payload.get("contact_id")
    )
    product_id = payload.get("product_id")
    if product_id is not None:
        await _ensure_product_in_account(
            session, account_id=account_id, product_id=product_id
        )

    starts_at = _coerce_datetime(
        payload.get("starts_at"), field_name="starts_at"
    )
    raw_ends = payload.get("ends_at")
    ends_at = (
        _coerce_datetime(raw_ends, field_name="ends_at")
        if raw_ends is not None
        else None
    )
    _validate_time_range(starts_at, ends_at)

    status = _validate_status(
        payload.get("status", APPOINTMENT_STATUS_SCHEDULED)
    )

    appointment = Appointment(
        account_id=account_id,
        contact_id=payload["contact_id"],
        product_id=product_id,
        title=title,
        description=payload.get("description"),
        starts_at=starts_at,
        ends_at=ends_at,
        status=status,
        notes=payload.get("notes"),
        created_by_id=created_by_id,
        external_id=payload.get("external_id"),
    )
    session.add(appointment)
    await session.flush()
    await session.refresh(appointment)
    if emit_event:
        await dispatcher.dispatch(
            session, APPOINTMENT_CREATED, appointment=appointment
        )
    return appointment


async def list_appointments(
    session: AsyncSession,
    *,
    account_id: int,
    starts_from: datetime | str | None = None,
    starts_to: datetime | str | None = None,
    contact_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> list[Appointment]:
    per_page = min(max(1, per_page), 200)
    page = max(1, page)

    stmt = (
        select(Appointment)
        .where(Appointment.account_id == account_id)
        .execution_options(populate_existing=True)
    )
    if starts_from is not None:
        dt_from = _coerce_datetime(starts_from, field_name="from")
        stmt = stmt.where(Appointment.starts_at >= dt_from)
    if starts_to is not None:
        dt_to = _coerce_datetime(starts_to, field_name="to")
        stmt = stmt.where(Appointment.starts_at < dt_to)
    if contact_id is not None:
        stmt = stmt.where(Appointment.contact_id == contact_id)
    if status is not None:
        valid_status = _validate_status(status)
        stmt = stmt.where(Appointment.status == valid_status)

    stmt = stmt.order_by(
        Appointment.starts_at.asc(),  # type: ignore[attr-defined]
        Appointment.id.asc(),  # type: ignore[union-attr]
    )
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    return list((await session.exec(stmt)).all())


async def get_appointment(
    session: AsyncSession, *, account_id: int, appointment_id: int
) -> Appointment | None:
    return (
        await session.exec(
            select(Appointment)
            .where(
                Appointment.id == appointment_id,
                Appointment.account_id == account_id,
            )
            .execution_options(populate_existing=True)
        )
    ).first()


async def update_appointment(
    session: AsyncSession,
    *,
    appointment: Appointment,
    payload: dict[str, Any],
) -> Appointment:
    before = {key: getattr(appointment, key) for key in _EVENT_ATTRIBUTES}
    if "title" in payload and payload["title"] is not None:
        appointment.title = _validate_title(payload["title"])
    elif "title" in payload and payload["title"] is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "title is required"},
        )

    if "contact_id" in payload:
        if payload["contact_id"] is None:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "contact_id is required"},
            )
        await _ensure_contact_in_account(
            session,
            account_id=appointment.account_id,
            contact_id=payload["contact_id"],
        )
        appointment.contact_id = payload["contact_id"]

    if "product_id" in payload:
        new_product_id = payload["product_id"]
        if new_product_id is not None:
            await _ensure_product_in_account(
                session,
                account_id=appointment.account_id,
                product_id=new_product_id,
            )
        appointment.product_id = new_product_id

    new_starts_at = appointment.starts_at
    if "starts_at" in payload:
        new_starts_at = _coerce_datetime(
            payload["starts_at"], field_name="starts_at"
        )

    new_ends_at = appointment.ends_at
    if "ends_at" in payload:
        raw_ends = payload["ends_at"]
        new_ends_at = (
            _coerce_datetime(raw_ends, field_name="ends_at")
            if raw_ends is not None
            else None
        )

    _validate_time_range(new_starts_at, new_ends_at)
    appointment.starts_at = new_starts_at
    appointment.ends_at = new_ends_at

    if "status" in payload and payload["status"] is not None:
        appointment.status = _validate_status(payload["status"])
    elif "status" in payload and payload["status"] is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "status is required"},
        )

    for field in ("description", "notes"):
        if field in payload:
            setattr(appointment, field, payload[field])

    session.add(appointment)
    await session.flush()
    await session.refresh(appointment)
    # Same shape as Rails' ``previous_changes``: {attr: [previous, current]}.
    changes = {
        key: [before[key], getattr(appointment, key)]
        for key in _EVENT_ATTRIBUTES
        if before[key] != getattr(appointment, key)
    }
    if changes:
        await dispatcher.dispatch(
            session,
            APPOINTMENT_UPDATED,
            appointment=appointment,
            changed_attributes=changes,
        )
    return appointment


async def delete_appointment(
    session: AsyncSession, *, appointment: Appointment
) -> None:
    await session.delete(appointment)
    await session.flush()


__all__ = [
    "create_appointment",
    "delete_appointment",
    "get_appointment",
    "list_appointments",
    "update_appointment",
]
