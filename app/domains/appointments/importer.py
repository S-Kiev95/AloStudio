"""Idempotent Postiz CRM importer (customers -> contacts, products, appointments)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import lazyload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.accounts.models import Account
from app.domains.appointments import service as asvc
from app.domains.appointments.models import Appointment
from app.domains.appointments.service import (
    _coerce_datetime,
    _validate_status,
    _validate_time_range,
    _validate_title,
)
from app.domains.contacts.models import Contact, Note
from app.domains.labels.models import DEFAULT_LABEL_COLOR, Label
from app.domains.products import service as psvc
from app.domains.products.models import Product


@dataclass
class ImportStats:
    contacts_created: int = 0
    contacts_reused: int = 0
    notes_created: int = 0
    labels_created: int = 0
    products_created: int = 0
    products_reused: int = 0
    appointments_created: int = 0
    appointments_reused: int = 0


def _normalize_label_title(raw: str) -> str:
    cleaned = re.sub(r"[^\w-]+", "-", raw.strip().lower(), flags=re.UNICODE)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned


def _parse_price(raw: Any) -> Decimal | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid product price: {raw!r}") from exc


async def _find_contact_for_customer(
    session: AsyncSession,
    *,
    account_id: int,
    cust_id: str,
    external_contact_id: Any,
    email: str | None,
    phone: str | None,
) -> Contact | None:
    # 1. Idempotency check: already imported from Postiz
    by_postiz = (
        await session.exec(
            select(Contact)
            .where(
                Contact.account_id == account_id,
                Contact.custom_attributes["postiz_crm_id"].astext == cust_id,
            )
            .options(lazyload("*"))
        )
    ).first()
    if by_postiz is not None:
        return by_postiz

    # 2. Explicit externalContactId in this account
    if external_contact_id is not None and not isinstance(
        external_contact_id, bool
    ):
        try:
            ext_id = int(external_contact_id)
        except (TypeError, ValueError):
            ext_id = None
        if ext_id is not None:
            by_ext = (
                await session.exec(
                    select(Contact)
                    .where(
                        Contact.account_id == account_id,
                        Contact.id == ext_id,
                    )
                    .options(lazyload("*"))
                )
            ).first()
            if by_ext is not None:
                return by_ext

    # 3. Email match (case-insensitive)
    if email:
        by_email = (
            await session.exec(
                select(Contact)
                .where(
                    Contact.account_id == account_id,
                    func.lower(Contact.email) == email,
                )
                .options(lazyload("*"))
            )
        ).first()
        if by_email is not None:
            return by_email

    # 4. Phone match
    if phone:
        by_phone = (
            await session.exec(
                select(Contact)
                .where(
                    Contact.account_id == account_id,
                    Contact.phone_number == phone,
                )
                .options(lazyload("*"))
            )
        ).first()
        if by_phone is not None:
            return by_phone

    return None


async def import_postiz_crm(
    session: AsyncSession,
    *,
    account_id: int,
    data: dict[str, Any],
    dry_run: bool = False,
    log: Callable[[str], None] | None = None,
) -> ImportStats:
    emit = log or (lambda _msg: None)
    account = (
        await session.exec(
            select(Account)
            .where(Account.id == account_id)
            .options(lazyload("*"))
        )
    ).first()
    if account is None:
        raise ValueError(f"La cuenta {account_id} no existe")

    stats = ImportStats()
    customers = data.get("customers") or []
    products = data.get("products") or []
    appointments = data.get("appointments") or []

    # Map Postiz IDs -> AloStudio IDs (None in dry_run when newly simulated)
    customer_map: dict[str, int | None] = {}
    product_map: dict[str, int | None] = {}

    existing_labels = {
        lab.title
        for lab in (
            await session.exec(
                select(Label).where(Label.account_id == account_id)
            )
        ).all()
    }

    # --- 1. Customers -> Contacts -----------------------------------------
    for cust in customers:
        cust_id = str(cust["id"]).strip()
        raw_name = (cust.get("name") or "").strip()
        raw_email = (cust.get("email") or "").strip().lower() or None
        raw_phone = (cust.get("phone") or "").strip() or None
        raw_notes = (cust.get("notes") or "").strip() or None
        raw_tags = [
            str(t).strip() for t in (cust.get("tags") or []) if str(t).strip()
        ]
        incoming_attrs = dict(cust.get("customAttributes") or {})

        norm_tags = [
            nt for nt in (_normalize_label_title(t) for t in raw_tags) if nt
        ]
        for nt in norm_tags:
            if nt not in existing_labels:
                existing_labels.add(nt)
                stats.labels_created += 1
                if dry_run:
                    emit(f"[dry-run] Crearía etiqueta: {nt}")
                else:
                    session.add(
                        Label(
                            account_id=account_id,
                            title=nt,
                            color=DEFAULT_LABEL_COLOR,
                        )
                    )
                    await session.flush()

        existing_contact = await _find_contact_for_customer(
            session,
            account_id=account_id,
            cust_id=cust_id,
            external_contact_id=cust.get("externalContactId"),
            email=raw_email,
            phone=raw_phone,
        )

        if existing_contact is not None:
            stats.contacts_reused += 1
            customer_map[cust_id] = existing_contact.id
            if dry_run:
                emit(
                    f"[dry-run] Reutilizaría contacto #{existing_contact.id} "
                    f"para cliente {cust_id} ({raw_name or raw_email or raw_phone})"
                )
            else:
                merged_attrs = dict(incoming_attrs)
                merged_attrs.update(existing_contact.custom_attributes or {})
                merged_attrs["postiz_crm_id"] = cust_id
                if norm_tags:
                    prev_tags = list(merged_attrs.get("tags") or [])
                    for nt in norm_tags:
                        if nt not in prev_tags:
                            prev_tags.append(nt)
                    merged_attrs["tags"] = prev_tags
                existing_contact.custom_attributes = merged_attrs
                if not (existing_contact.name or "").strip() and raw_name:
                    existing_contact.name = raw_name
                if not existing_contact.phone_number and raw_phone:
                    existing_contact.phone_number = raw_phone
                session.add(existing_contact)
                await session.flush()
            target_contact_id = existing_contact.id
        else:
            stats.contacts_created += 1
            if dry_run:
                customer_map[cust_id] = None
                target_contact_id = None
                emit(
                    f"[dry-run] Crearía contacto para cliente {cust_id}: "
                    f"{raw_name or raw_email or raw_phone}"
                )
            else:
                attrs = dict(incoming_attrs)
                attrs["postiz_crm_id"] = cust_id
                if norm_tags:
                    attrs["tags"] = list(dict.fromkeys(norm_tags))
                new_contact = Contact(
                    account_id=account_id,
                    name=raw_name,
                    email=raw_email,
                    phone_number=raw_phone,
                    custom_attributes=attrs,
                    additional_attributes={},
                )
                session.add(new_contact)
                await session.flush()
                await session.refresh(new_contact)
                customer_map[cust_id] = new_contact.id
                target_contact_id = new_contact.id

        if raw_notes:
            already_has_note = False
            if target_contact_id is not None:
                dup_note = (
                    await session.exec(
                        select(Note.id).where(
                            Note.account_id == account_id,
                            Note.contact_id == target_contact_id,
                            Note.content == raw_notes,
                        )
                    )
                ).first()
                already_has_note = dup_note is not None
            if not already_has_note:
                stats.notes_created += 1
                if dry_run:
                    emit(
                        f"[dry-run] Agregaría nota al cliente {cust_id}"
                    )
                else:
                    assert target_contact_id is not None
                    session.add(
                        Note(
                            account_id=account_id,
                            contact_id=target_contact_id,
                            content=raw_notes,
                        )
                    )
                    await session.flush()

    # --- 2. Products ------------------------------------------------------
    for prod in products:
        prod_id = str(prod["id"]).strip()
        existing_prod = (
            await session.exec(
                select(Product).where(
                    Product.account_id == account_id,
                    Product.external_id == prod_id,
                )
            )
        ).first()
        if existing_prod is not None:
            stats.products_reused += 1
            product_map[prod_id] = existing_prod.id
            if dry_run:
                emit(
                    f"[dry-run] Reutilizaría producto #{existing_prod.id} ({prod_id})"
                )
            continue

        price_val = _parse_price(prod.get("price"))
        stats.products_created += 1
        if dry_run:
            product_map[prod_id] = None
            emit(f"[dry-run] Crearía producto ({prod_id}): {prod.get('name')}")
        else:
            created_prod = await psvc.create_product(
                session,
                account_id=account_id,
                payload={
                    "name": prod["name"],
                    "sku": prod.get("sku"),
                    "description": prod.get("description"),
                    "price": price_val,
                    "currency": prod.get("currency"),
                    "url": prod.get("url"),
                    "image_url": prod.get("imageUrl"),
                    "enabled": bool(prod.get("enabled", True)),
                    "external_id": prod_id,
                },
            )
            product_map[prod_id] = created_prod.id

    # --- 3. Appointments --------------------------------------------------
    for appt in appointments:
        appt_id = str(appt["id"]).strip()
        existing_appt = (
            await session.exec(
                select(Appointment).where(
                    Appointment.account_id == account_id,
                    Appointment.external_id == appt_id,
                )
            )
        ).first()
        if existing_appt is not None:
            stats.appointments_reused += 1
            if dry_run:
                emit(
                    f"[dry-run] Reutilizaría cita #{existing_appt.id} ({appt_id})"
                )
            continue

        cust_ref = str(appt["customerId"]).strip()
        if cust_ref in customer_map:
            resolved_contact_id = customer_map[cust_ref]
        else:
            db_contact = (
                await session.exec(
                    select(Contact.id).where(
                        Contact.account_id == account_id,
                        Contact.custom_attributes["postiz_crm_id"].astext
                        == cust_ref,
                    )
                )
            ).first()
            if db_contact is None:
                raise ValueError(
                    f"Cita {appt_id} referencia un customerId desconocido: {cust_ref}"
                )
            resolved_contact_id = db_contact

        prod_ref_raw = appt.get("productId")
        resolved_product_id: int | None = None
        if prod_ref_raw:
            prod_ref = str(prod_ref_raw).strip()
            if prod_ref in product_map:
                resolved_product_id = product_map[prod_ref]
            else:
                db_prod = (
                    await session.exec(
                        select(Product.id).where(
                            Product.account_id == account_id,
                            Product.external_id == prod_ref,
                        )
                    )
                ).first()
                if db_prod is None:
                    raise ValueError(
                        f"Cita {appt_id} referencia un productId desconocido: {prod_ref}"
                    )
                resolved_product_id = db_prod

        status_lower = _validate_status(
            str(appt.get("status") or "SCHEDULED").strip().lower()
        )
        title = _validate_title(appt.get("title"))
        starts_dt = _coerce_datetime(
            appt.get("startDate"), field_name="startDate"
        )
        ends_raw = appt.get("endDate")
        ends_dt = (
            _coerce_datetime(ends_raw, field_name="endDate")
            if ends_raw is not None
            else None
        )
        _validate_time_range(starts_dt, ends_dt)

        stats.appointments_created += 1
        if dry_run:
            emit(f"[dry-run] Crearía cita ({appt_id}): {title}")
        else:
            assert resolved_contact_id is not None
            await asvc.create_appointment(
                session,
                account_id=account_id,
                payload={
                    "contact_id": resolved_contact_id,
                    "product_id": resolved_product_id,
                    "title": title,
                    "description": appt.get("description"),
                    "starts_at": starts_dt,
                    "ends_at": ends_dt,
                    "status": status_lower,
                    "notes": appt.get("notes"),
                    "external_id": appt_id,
                },
            )

    return stats


__all__ = ["ImportStats", "import_postiz_crm"]
