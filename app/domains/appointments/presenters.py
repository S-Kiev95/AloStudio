"""Wire-shape presenter for appointments."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.orm import lazyload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.appointments.models import Appointment
from app.domains.contacts.models import Contact
from app.domains.products.models import Product


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def present_appointment(
    appointment: Appointment,
    *,
    contact: Contact | None = None,
    product: Product | None = None,
) -> dict[str, Any]:
    return {
        "id": appointment.id,
        "account_id": appointment.account_id,
        "contact_id": appointment.contact_id,
        "product_id": appointment.product_id,
        "title": appointment.title,
        "description": appointment.description,
        "starts_at": _iso(appointment.starts_at),
        "ends_at": _iso(appointment.ends_at),
        "status": appointment.status,
        "notes": appointment.notes,
        "created_by_id": appointment.created_by_id,
        "created_at": _iso(appointment.created_at),
        "updated_at": _iso(appointment.updated_at),
        "contact": (
            {
                "id": contact.id,
                "name": contact.name,
                "email": contact.email,
                "phone_number": contact.phone_number,
            }
            if contact is not None
            else None
        ),
        "product": (
            {
                "id": product.id,
                "name": product.name,
                "price": (
                    float(product.price) if product.price is not None else None
                ),
                "currency": product.currency,
            }
            if product is not None
            else None
        ),
    }


async def present_appointments(
    session: AsyncSession, appointments: Sequence[Appointment]
) -> list[dict[str, Any]]:
    """Batch-load related contacts and products without N+1 queries."""
    if not appointments:
        return []

    contact_ids = {a.contact_id for a in appointments}
    product_ids = {
        a.product_id for a in appointments if a.product_id is not None
    }

    contacts_by_id: dict[int, Contact] = {}
    if contact_ids:
        c_rows = (
            await session.exec(
                select(Contact)
                .where(Contact.id.in_(contact_ids))  # type: ignore[union-attr]
                .options(lazyload("*"))
            )
        ).all()
        contacts_by_id = {c.id: c for c in c_rows if c.id is not None}

    products_by_id: dict[int, Product] = {}
    if product_ids:
        p_rows = (
            await session.exec(
                select(Product).where(
                    Product.id.in_(product_ids)  # type: ignore[union-attr]
                )
            )
        ).all()
        products_by_id = {p.id: p for p in p_rows if p.id is not None}

    return [
        present_appointment(
            a,
            contact=contacts_by_id.get(a.contact_id),
            product=(
                products_by_id.get(a.product_id)
                if a.product_id is not None
                else None
            ),
        )
        for a in appointments
    ]


async def present_one_appointment(
    session: AsyncSession, appointment: Appointment
) -> dict[str, Any]:
    items = await present_appointments(session, [appointment])
    return items[0]


__all__ = [
    "present_appointment",
    "present_appointments",
    "present_one_appointment",
]
