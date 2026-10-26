"""Integration tests for the Postiz CRM importer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import select

from app.core.models_registry import import_all_models
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.appointments.importer import import_postiz_crm
from app.domains.appointments.models import Appointment
from app.domains.contacts.models import Contact, Note
from app.domains.contacts.service import create_contact
from app.domains.labels.models import Label
from app.domains.products.models import Product

import_all_models()

pytestmark = pytest.mark.integration


async def _seed_account(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"imp{suffix}@agenda.example.com",
            account_name=f"IMP{suffix}",
            user_full_name=f"Imp{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    return owner.account


async def test_import_postiz_crm_dry_run_and_idempotent(
    db_session, tmp_path: Path
):
    account = await _seed_account(db_session, "-idem")

    # Existing contacts to verify externalContactId, email, and phone resolution
    c_by_ext = await create_contact(
        db_session,
        account_id=account.id,
        payload={"name": "Por External ID", "email": "ext@example.com"},
    )
    c_by_email = await create_contact(
        db_session,
        account_id=account.id,
        payload={"name": "Por Email", "email": "lucia@example.com"},
    )
    c_by_phone = await create_contact(
        db_session,
        account_id=account.id,
        payload={"name": "Por Teléfono", "phone_number": "+59899888777"},
    )

    sample = {
        "customers": [
            {
                "id": "ckx_cust_ext",
                "name": "Nombre Postiz Ext",
                "email": None,
                "phone": None,
                "notes": "Cliente vinculado por ID externo",
                "tags": ["VIP", "Frecuente"],
                "customAttributes": {"origen": "instagram"},
                "externalContactId": c_by_ext.id,
            },
            {
                "id": "ckx_cust_mail",
                "name": "Lucía",
                "email": "LUCIA@example.com",
                "phone": None,
                "notes": None,
                "tags": ["VIP"],
                "customAttributes": {},
                "externalContactId": None,
            },
            {
                "id": "ckx_cust_tel",
                "name": "Martín",
                "email": None,
                "phone": "+59899888777",
                "notes": None,
                "tags": [],
                "customAttributes": {},
                "externalContactId": 99999999,
            },
            {
                "id": "ckx_cust_new",
                "name": "Sofía Nueva",
                "email": "sofia@example.com",
                "phone": "+59891000111",
                "notes": "Prefiere horario matutino",
                "tags": ["Nuevo Cliente"],
                "customAttributes": {"plan": "anual"},
                "externalContactId": None,
            },
        ],
        "products": [
            {
                "id": "ckx_prod_1",
                "name": "Sesión Integral",
                "sku": "SES-01",
                "description": "Sesión de 60 minutos",
                "price": "1200.00",
                "currency": "UYU",
                "url": "https://ejemplo.uy/sesion",
                "imageUrl": None,
                "enabled": True,
            }
        ],
        "appointments": [
            {
                "id": "ckx_appt_1",
                "customerId": "ckx_cust_new",
                "productId": "ckx_prod_1",
                "title": "Primera consulta Sofía",
                "description": "Evaluación",
                "startDate": "2026-10-28T13:00:00.000Z",
                "endDate": "2026-10-28T14:00:00.000Z",
                "status": "CONFIRMED",
                "notes": "Puntual",
            },
            {
                "id": "ckx_appt_2",
                "customerId": "ckx_cust_ext",
                "productId": None,
                "title": "Seguimiento",
                "description": None,
                "startDate": "2026-10-29T15:00:00.000Z",
                "endDate": None,
                "status": "SCHEDULED",
                "notes": None,
            },
        ],
    }

    export_file = tmp_path / "export.json"
    export_file.write_text(json.dumps(sample), encoding="utf-8")
    loaded = json.loads(export_file.read_text(encoding="utf-8"))

    # 1. Dry-run writes nothing
    logs: list[str] = []
    dry_stats = await import_postiz_crm(
        db_session,
        account_id=account.id,
        data=loaded,
        dry_run=True,
        log=logs.append,
    )
    assert dry_stats.contacts_created == 1
    assert dry_stats.contacts_reused == 3
    assert dry_stats.notes_created == 2
    assert dry_stats.labels_created == 3
    assert dry_stats.products_created == 1
    assert dry_stats.appointments_created == 2
    assert any("[dry-run]" in line for line in logs)

    # Confirm DB has 0 products and 0 appointments after dry-run
    assert (
        list(
            (
                await db_session.exec(
                    select(Product).where(Product.account_id == account.id)
                )
            ).all()
        )
        == []
    )
    assert (
        list(
            (
                await db_session.exec(
                    select(Appointment).where(
                        Appointment.account_id == account.id
                    )
                )
            ).all()
        )
        == []
    )

    # 2. First real run creates everything
    first = await import_postiz_crm(
        db_session,
        account_id=account.id,
        data=loaded,
        dry_run=False,
    )
    assert first.contacts_created == 1
    assert first.contacts_reused == 3
    assert first.notes_created == 2
    assert first.labels_created == 3
    assert first.products_created == 1
    assert first.appointments_created == 2

    # 3. Second real run is completely idempotent (0 new rows anywhere)
    second = await import_postiz_crm(
        db_session,
        account_id=account.id,
        data=loaded,
        dry_run=False,
    )
    assert second.contacts_created == 0
    assert second.contacts_reused == 4
    assert second.notes_created == 0
    assert second.labels_created == 0
    assert second.products_created == 0
    assert second.products_reused == 1
    assert second.appointments_created == 0
    assert second.appointments_reused == 2

    # Verify DB state
    contacts = list(
        (
            await db_session.exec(
                select(Contact).where(Contact.account_id == account.id)
            )
        ).all()
    )
    assert len(contacts) == 4
    by_crm_id = {
        c.custom_attributes.get("postiz_crm_id"): c for c in contacts
    }
    assert by_crm_id["ckx_cust_ext"].id == c_by_ext.id
    assert by_crm_id["ckx_cust_mail"].id == c_by_email.id
    assert by_crm_id["ckx_cust_tel"].id == c_by_phone.id
    sofia = by_crm_id["ckx_cust_new"]
    assert sofia.name == "Sofía Nueva"
    assert sofia.custom_attributes["plan"] == "anual"
    assert "nuevo-cliente" in sofia.custom_attributes["tags"]

    notes = list(
        (
            await db_session.exec(
                select(Note).where(Note.account_id == account.id)
            )
        ).all()
    )
    assert len(notes) == 2

    labels = list(
        (
            await db_session.exec(
                select(Label).where(Label.account_id == account.id)
            )
        ).all()
    )
    assert {lab.title for lab in labels} == {
        "vip",
        "frecuente",
        "nuevo-cliente",
    }

    prods = list(
        (
            await db_session.exec(
                select(Product).where(Product.account_id == account.id)
            )
        ).all()
    )
    assert len(prods) == 1
    assert prods[0].external_id == "ckx_prod_1"
    assert float(prods[0].price) == 1200.0

    appts = list(
        (
            await db_session.exec(
                select(Appointment).where(
                    Appointment.account_id == account.id
                )
            )
        ).all()
    )
    assert len(appts) == 2
    appts_by_ext = {a.external_id: a for a in appts}
    assert appts_by_ext["ckx_appt_1"].status == "confirmed"
    assert appts_by_ext["ckx_appt_1"].contact_id == sofia.id
    assert appts_by_ext["ckx_appt_1"].product_id == prods[0].id
    assert appts_by_ext["ckx_appt_2"].status == "scheduled"
    assert appts_by_ext["ckx_appt_2"].contact_id == c_by_ext.id
    assert appts_by_ext["ckx_appt_2"].product_id is None
