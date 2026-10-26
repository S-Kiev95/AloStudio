"""Integration tests for the CRM appointments (agenda) domain."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.appointments import service as asvc
from app.domains.contacts.models import Contact
from app.domains.contacts.service import create_contact
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.products import service as psvc
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@agenda.example.com",
            account_name=f"AGENDA{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _seed_agent(db_session, account_id: int, suffix: str):
    agent_owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@agenda.example.com",
            account_name=f"AGENTORG{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=account_id,
            user_id=agent_owner.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=agent_owner.user.tokens, uid=agent_owner.user.uid
    )
    agent_owner.user.tokens = new_tokens
    db_session.add(agent_owner.user)
    await db_session.flush()
    return agent_owner.user, headers.as_response_headers()


async def _seed_contact(
    db_session, account_id: int, suffix: str
) -> Contact:
    return await create_contact(
        db_session,
        account_id=account_id,
        payload={
            "name": f"Cliente {suffix}",
            "email": f"cliente{suffix}@example.com",
            "phone_number": "+59899123456",
        },
    )


# ---------------------------------------------------------------------------
# Auth & CRUD
# ---------------------------------------------------------------------------
async def test_appointments_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/appointments")
    assert resp.status_code == 401


async def test_appointment_crud_endpoints(client, db_session):
    owner, headers = await _seed_admin(db_session, "-crud")
    contact = await _seed_contact(db_session, owner.account.id, "-crud")
    product = await psvc.create_product(
        db_session,
        account_id=owner.account.id,
        payload={"name": "Consulta inicial", "price": 1500.0, "currency": "UYU"},
    )

    starts = datetime(2026, 10, 27, 14, 0, tzinfo=UTC)
    ends = starts + timedelta(hours=1)

    create_resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/appointments",
        json={
            "contact_id": contact.id,
            "product_id": product.id,
            "title": "Reunión de diagnóstico",
            "description": "Primera sesión",
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "notes": "Traer estudios",
        },
        headers=headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    body = create_resp.json()
    aid = body["id"]
    assert body["title"] == "Reunión de diagnóstico"
    assert body["status"] == "scheduled"
    assert body["created_by_id"] == owner.user.id
    assert body["contact"] == {
        "id": contact.id,
        "name": contact.name,
        "email": contact.email,
        "phone_number": contact.phone_number,
    }
    assert body["product"] == {
        "id": product.id,
        "name": "Consulta inicial",
        "price": 1500.0,
        "currency": "UYU",
    }
    assert datetime.fromisoformat(body["starts_at"]) == starts
    assert datetime.fromisoformat(body["ends_at"]) == ends

    # Show
    show_resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/appointments/{aid}",
        headers=headers,
    )
    assert show_resp.status_code == 200
    assert show_resp.json()["id"] == aid

    # Patch
    patch_resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/appointments/{aid}",
        json={"status": "confirmed", "title": "Reunión confirmada"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "confirmed"
    assert patch_resp.json()["title"] == "Reunión confirmada"

    # Delete (physical delete)
    del_resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/appointments/{aid}",
        headers=headers,
    )
    assert del_resp.status_code == 200
    assert del_resp.json() == {}

    after_del = await client.get(
        f"/api/v1/accounts/{owner.account.id}/appointments/{aid}",
        headers=headers,
    )
    assert after_del.status_code == 404


# ---------------------------------------------------------------------------
# Filters & ordering
# ---------------------------------------------------------------------------
async def test_appointments_filters_and_asc_order(client, db_session):
    owner, headers = await _seed_admin(db_session, "-flt")
    c1 = await _seed_contact(db_session, owner.account.id, "-flt1")
    c2 = await create_contact(
        db_session,
        account_id=owner.account.id,
        payload={"name": "Otro", "email": "otro-flt@example.com"},
    )

    t1 = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    t3 = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)

    # Insert out of chronological order to verify ascending order on starts_at.
    a2 = await asvc.create_appointment(
        db_session,
        account_id=owner.account.id,
        payload={
            "contact_id": c1.id,
            "title": "Cita 2",
            "starts_at": t2,
            "status": "confirmed",
        },
    )
    a1 = await asvc.create_appointment(
        db_session,
        account_id=owner.account.id,
        payload={
            "contact_id": c1.id,
            "title": "Cita 1",
            "starts_at": t1,
            "status": "scheduled",
        },
    )
    a3 = await asvc.create_appointment(
        db_session,
        account_id=owner.account.id,
        payload={
            "contact_id": c2.id,
            "title": "Cita 3",
            "starts_at": t3,
            "status": "done",
        },
    )

    # Unfiltered -> ascending starts_at
    all_resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/appointments", headers=headers
    )
    assert all_resp.status_code == 200
    assert [x["id"] for x in all_resp.json()] == [a1.id, a2.id, a3.id]

    # Date range: from inclusive (t1), to exclusive (t3) -> returns a1 and a2 only
    range_resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/appointments",
        params={"from": t1.isoformat(), "to": t3.isoformat()},
        headers=headers,
    )
    assert range_resp.status_code == 200
    assert [x["id"] for x in range_resp.json()] == [a1.id, a2.id]

    # Filter by status
    st_resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/appointments",
        params={"status": "confirmed"},
        headers=headers,
    )
    assert st_resp.status_code == 200
    assert [x["id"] for x in st_resp.json()] == [a2.id]

    # Filter by contact_id
    ct_resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/appointments",
        params={"contact_id": c2.id},
        headers=headers,
    )
    assert ct_resp.status_code == 200
    assert [x["id"] for x in ct_resp.json()] == [a3.id]


# ---------------------------------------------------------------------------
# Validations & cross-account isolation
# ---------------------------------------------------------------------------
async def test_ends_at_before_starts_at_returns_422(client, db_session):
    owner, headers = await _seed_admin(db_session, "-dates")
    contact = await _seed_contact(db_session, owner.account.id, "-dates")
    starts = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)
    ends = starts - timedelta(minutes=30)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/appointments",
        json={
            "contact_id": contact.id,
            "title": "Rango inválido",
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 422

    # Valid create followed by invalid PATCH also returns 422
    ok = await client.post(
        f"/api/v1/accounts/{owner.account.id}/appointments",
        json={
            "contact_id": contact.id,
            "title": "Cita válida",
            "starts_at": starts.isoformat(),
        },
        headers=headers,
    )
    assert ok.status_code == 200
    aid = ok.json()["id"]

    bad_patch = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/appointments/{aid}",
        json={"ends_at": ends.isoformat()},
        headers=headers,
    )
    assert bad_patch.status_code == 422


async def test_foreign_contact_or_product_returns_422(client, db_session):
    owner_a, headers_a = await _seed_admin(db_session, "-ownA")
    owner_b, _ = await _seed_admin(db_session, "-ownB")

    contact_a = await _seed_contact(db_session, owner_a.account.id, "-ownA")
    contact_b = await _seed_contact(db_session, owner_b.account.id, "-ownB")
    product_b = await psvc.create_product(
        db_session, account_id=owner_b.account.id, payload={"name": "Ajeno"}
    )

    starts = datetime(2026, 10, 28, 12, 0, tzinfo=UTC).isoformat()

    # Foreign contact -> 422
    r_contact = await client.post(
        f"/api/v1/accounts/{owner_a.account.id}/appointments",
        json={
            "contact_id": contact_b.id,
            "title": "Contacto ajeno",
            "starts_at": starts,
        },
        headers=headers_a,
    )
    assert r_contact.status_code == 422

    # Foreign product -> 422
    r_prod = await client.post(
        f"/api/v1/accounts/{owner_a.account.id}/appointments",
        json={
            "contact_id": contact_a.id,
            "product_id": product_b.id,
            "title": "Producto ajeno",
            "starts_at": starts,
        },
        headers=headers_a,
    )
    assert r_prod.status_code == 422


async def test_appointment_of_other_account_returns_404(client, db_session):
    owner_a, headers_a = await _seed_admin(db_session, "-isoA")
    owner_b, _ = await _seed_admin(db_session, "-isoB")
    contact_b = await _seed_contact(db_session, owner_b.account.id, "-isoB")

    appt_b = await asvc.create_appointment(
        db_session,
        account_id=owner_b.account.id,
        payload={
            "contact_id": contact_b.id,
            "title": "Secreta",
            "starts_at": datetime(2026, 10, 29, 9, 0, tzinfo=UTC),
        },
    )

    for method, kwargs in (
        ("get", {}),
        ("patch", {"json": {"status": "cancelled"}}),
        ("delete", {}),
    ):
        resp = await getattr(client, method)(
            f"/api/v1/accounts/{owner_a.account.id}/appointments/{appt_b.id}",
            headers=headers_a,
            **kwargs,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Permissions & FK ON DELETE SET NULL
# ---------------------------------------------------------------------------
async def test_agent_can_create_update_and_delete_appointment(client, db_session):
    owner, _ = await _seed_admin(db_session, "-agperm")
    agent_user, agent_headers = await _seed_agent(
        db_session, owner.account.id, "-agperm"
    )
    contact = await _seed_contact(db_session, owner.account.id, "-agperm")

    create_resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/appointments",
        json={
            "contact_id": contact.id,
            "title": "Cargada por agente",
            "starts_at": datetime(2026, 10, 30, 11, 0, tzinfo=UTC).isoformat(),
        },
        headers=agent_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    assert create_resp.json()["created_by_id"] == agent_user.id
    aid = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/appointments/{aid}",
        json={"status": "done"},
        headers=agent_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "done"

    del_resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/appointments/{aid}",
        headers=agent_headers,
    )
    assert del_resp.status_code == 200


async def test_deleting_product_sets_appointment_product_id_to_null(
    client, db_session
):
    owner, headers = await _seed_admin(db_session, "-prodnull")
    contact = await _seed_contact(db_session, owner.account.id, "-prodnull")
    product = await psvc.create_product(
        db_session,
        account_id=owner.account.id,
        payload={"name": "Servicio temporal"},
    )

    appt = await asvc.create_appointment(
        db_session,
        account_id=owner.account.id,
        payload={
            "contact_id": contact.id,
            "product_id": product.id,
            "title": "Cita con producto",
            "starts_at": datetime(2026, 10, 31, 16, 0, tzinfo=UTC),
        },
    )
    assert appt.product_id == product.id

    await psvc.delete_product(db_session, product=product)

    got = await client.get(
        f"/api/v1/accounts/{owner.account.id}/appointments/{appt.id}",
        headers=headers,
    )
    assert got.status_code == 200
    assert got.json()["product_id"] is None
    assert got.json()["product"] is None


async def test_service_rejects_blank_title_and_invalid_status(db_session):
    owner, _ = await _seed_admin(db_session, "-svcval")
    contact = await _seed_contact(db_session, owner.account.id, "-svcval")

    with pytest.raises(ChatwootHTTPException) as exc_title:
        await asvc.create_appointment(
            db_session,
            account_id=owner.account.id,
            payload={
                "contact_id": contact.id,
                "title": "   ",
                "starts_at": datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
            },
        )
    assert exc_title.value.status_code == 422

    with pytest.raises(ChatwootHTTPException) as exc_status:
        await asvc.create_appointment(
            db_session,
            account_id=owner.account.id,
            payload={
                "contact_id": contact.id,
                "title": "Ok",
                "starts_at": datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
                "status": "pending",
            },
        )
    assert exc_status.value.status_code == 422
