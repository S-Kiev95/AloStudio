"""CRM collections (cobranzas): payment terms, installments, payments,
allocations, client statements, receivables, permissions, and conflict guards.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.inboxes.models import CHANNEL_TYPE_WHATSAPP, Inbox
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


async def _headers(db_session, user) -> dict[str, str]:
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@cobranzas.example.com",
            account_name=f"Cobranzas{suffix}",
            user_full_name="Ana Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    return owner, await _headers(db_session, owner.user)


async def _agent(db_session, owner, suffix: str):
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@cobranzas.example.com",
            account_name=f"CobranzasA{suffix}",
            user_full_name="Beto Agente",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id, user_id=agent.user.id, role=ACCOUNT_USER_ROLE_AGENT
        )
    )
    await db_session.flush()
    return agent, await _headers(db_session, agent.user)


def _base(owner) -> str:
    return f"/api/v1/accounts/{owner.account.id}/crm"


async def _stages(client: AsyncClient, owner, headers: dict[str, str]) -> dict[str, int]:
    resp = await client.get(f"{_base(owner)}/pipelines", headers=headers)
    assert resp.status_code == 200, resp.text
    return {s["code"]: s["id"] for s in resp.json()[0]["stages"]}


async def _make_contact(db_session, owner, name: str, phone: str | None = None) -> Contact:
    contact = Contact(account_id=owner.account.id, name=name, phone_number=phone)
    db_session.add(contact)
    await db_session.flush()
    return contact


async def _make_won_sale(
    client: AsyncClient,
    owner,
    headers: dict[str, str],
    stages: dict[str, int],
    *,
    title: str,
    value: float,
    currency: str | None,
    contact_id: int,
    owner_id: int | None = None,
) -> dict:
    body: dict = {
        "title": title,
        "value": value,
        "currency": currency,
        "contact_id": contact_id,
        "stage_id": stages["won"],
    }
    if owner_id is not None:
        body["owner_id"] = owner_id
    resp = await client.post(f"{_base(owner)}/opportunities", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_payment_terms_cash_one_step_and_open_opp_rejected(client, db_session):
    owner, h = await _seed(db_session, "-cash")
    stages = await _stages(client, owner, h)
    contact = await _make_contact(db_session, owner, "Lucía")

    # Open opportunity cannot configure billing terms.
    open_opp = (
        await client.post(
            f"{_base(owner)}/opportunities",
            json={"title": "Propuesta", "value": 500, "currency": "UYU", "contact_id": contact.id},
            headers=h,
        )
    ).json()
    assert open_opp["payment_terms"] is None
    resp = await client.put(
        f"{_base(owner)}/opportunities/{open_opp['id']}/billing",
        json={"payment_terms": "cash"},
        headers=h,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "opportunity_not_won"

    # Won sale billed as cash with one-step full payment.
    sale = await _make_won_sale(
        client,
        owner,
        h,
        stages,
        title="Curso contado",
        value=1500,
        currency="UYU",
        contact_id=contact.id,
    )
    resp = await client.put(
        f"{_base(owner)}/opportunities/{sale['id']}/billing",
        json={
            "payment_terms": "cash",
            "register_payment": True,
            "payment_method": "transfer",
            "paid_on": "2026-11-20",
            "payment_note": "Transferencia BROU",
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    billing = resp.json()
    assert billing["payment_terms"] == "cash"
    assert billing["paid_amount"] == 1500.0
    assert billing["owed_amount"] == 0.0
    assert billing["created_payment"]["amount"] == 1500.0
    assert billing["created_payment"]["method"] == "transfer"
    assert billing["created_payment"]["created_by"]["id"] == owner.user.id


async def test_installments_generation_rounding_and_manual_edits(client, db_session):
    owner, h = await _seed(db_session, "-inst")
    stages = await _stages(client, owner, h)
    contact = await _make_contact(db_session, owner, "Martín")

    # 100.00 / 3 -> 33.33, 33.33, 33.34; monthly from Jan 31 -> Feb 28 -> Mar 31.
    sale = await _make_won_sale(
        client,
        owner,
        h,
        stages,
        title="Plan trimestral",
        value=100,
        currency="USD",
        contact_id=contact.id,
    )
    resp = await client.put(
        f"{_base(owner)}/opportunities/{sale['id']}/billing",
        json={
            "payment_terms": "installments",
            "generate": {
                "count": 3,
                "first_due_on": "2026-01-31",
                "frequency": "monthly",
            },
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    insts = resp.json()["installments"]
    assert [(i["number"], i["due_on"], i["amount"]) for i in insts] == [
        (1, "2026-01-31", 33.33),
        (2, "2026-02-28", 33.33),
        (3, "2026-03-31", 33.34),
    ]

    # Regenerate every 15 days.
    resp = await client.put(
        f"{_base(owner)}/opportunities/{sale['id']}/billing",
        json={
            "payment_terms": "installments",
            "generate": {
                "count": 2,
                "first_due_on": "2026-11-01",
                "frequency": "every_n_days",
                "interval_days": 15,
            },
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    insts = resp.json()["installments"]
    assert [(i["number"], i["due_on"], i["amount"]) for i in insts] == [
        (1, "2026-11-01", 50.0),
        (2, "2026-11-16", 50.0),
    ]

    # Manual edit of unpaid installments (matching total).
    resp = await client.put(
        f"{_base(owner)}/opportunities/{sale['id']}/billing",
        json={
            "payment_terms": "installments",
            "installments": [
                {"due_on": "2026-11-05", "amount": 40},
                {"due_on": "2026-11-25", "amount": 60},
            ],
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    insts = resp.json()["installments"]
    assert [(i["due_on"], i["amount"]) for i in insts] == [
        ("2026-11-05", 40.0),
        ("2026-11-25", 60.0),
    ]

    # Sum mismatch rejected.
    bad = await client.put(
        f"{_base(owner)}/opportunities/{sale['id']}/billing",
        json={
            "payment_terms": "installments",
            "installments": [
                {"due_on": "2026-11-05", "amount": 40},
                {"due_on": "2026-11-25", "amount": 50},
            ],
        },
        headers=h,
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "installments_sum_mismatch"

    # Single installment due date edit works while unpaid.
    patch_ok = await client.patch(
        f"{_base(owner)}/opportunities/{sale['id']}/installments/{insts[0]['id']}",
        json={"due_on": "2026-11-08"},
        headers=h,
    )
    assert patch_ok.status_code == 200
    assert patch_ok.json()["installments"][0]["due_on"] == "2026-11-08"

    # Once a payment is allocated to installment 1, editing it is blocked.
    pay = await client.post(
        f"{_base(owner)}/payments",
        json={
            "contact_id": contact.id,
            "amount": 20,
            "currency": "USD",
            "paid_on": "2026-11-09",
            "method": "cash",
        },
        headers=h,
    )
    assert pay.status_code == 200, pay.text
    locked = await client.patch(
        f"{_base(owner)}/opportunities/{sale['id']}/installments/{insts[0]['id']}",
        json={"due_on": "2026-11-12"},
        headers=h,
    )
    assert locked.status_code == 422
    assert locked.json()["code"] == "installments_locked"


async def test_partial_payments_multi_sale_auto_allocation_and_credit_balance(client, db_session):
    owner, h = await _seed(db_session, "-auto")
    stages = await _stages(client, owner, h)
    contact = await _make_contact(db_session, owner, "Sofía")

    # Sale 1: fiado due 2026-11-10 for 500 UYU.
    s1 = await _make_won_sale(
        client,
        owner,
        h,
        stages,
        title="Venta vieja",
        value=500,
        currency="UYU",
        contact_id=contact.id,
    )
    await client.put(
        f"{_base(owner)}/opportunities/{s1['id']}/billing",
        json={"payment_terms": "credit", "due_on": "2026-11-10"},
        headers=h,
    )

    # Sale 2: installments due 2026-11-05 (300) and 2026-12-05 (300) for 600 UYU.
    s2 = await _make_won_sale(
        client,
        owner,
        h,
        stages,
        title="Venta en cuotas",
        value=600,
        currency="UYU",
        contact_id=contact.id,
    )
    await client.put(
        f"{_base(owner)}/opportunities/{s2['id']}/billing",
        json={
            "payment_terms": "installments",
            "generate": {"count": 2, "first_due_on": "2026-11-05", "frequency": "monthly"},
        },
        headers=h,
    )

    # Preview payment of 900 UYU: should allocate 300 to s2#1 (Nov 5), 500 to s1 (Nov 10), 100 to s2#2 (Dec 5).
    prev = await client.post(
        f"{_base(owner)}/payments/preview",
        json={
            "contact_id": contact.id,
            "amount": 900,
            "currency": "UYU",
            "allocation_mode": "auto",
        },
        headers=h,
    )
    assert prev.status_code == 200, prev.text
    pjson = prev.json()
    assert [
        (a["opportunity_id"], a["installment_number"], a["amount"]) for a in pjson["allocations"]
    ] == [
        (s2["id"], 1, 300.0),
        (s1["id"], None, 500.0),
        (s2["id"], 2, 100.0),
    ]
    assert pjson["balance_before"]["owed_total"] == 1100.0
    assert pjson["balance_after"]["owed_total"] == 200.0
    assert pjson["balance_after"]["credit_balance"] == 0.0

    # Register that payment of 900 UYU (one payment covering multiple sales + partial on s2#2).
    p1 = (
        await client.post(
            f"{_base(owner)}/payments",
            json={
                "contact_id": contact.id,
                "amount": 900,
                "currency": "UYU",
                "paid_on": "2026-11-15",
                "method": "transfer",
            },
            headers=h,
        )
    ).json()
    assert p1["allocated_amount"] == 900.0
    assert p1["unallocated_amount"] == 0.0

    # Second payment of 350 UYU: covers remaining 200 on s2#2 and leaves 150 as saldo a favor!
    p2 = (
        await client.post(
            f"{_base(owner)}/payments",
            json={
                "contact_id": contact.id,
                "amount": 350,
                "currency": "UYU",
                "paid_on": "2026-11-20",
                "method": "cash",
            },
            headers=h,
        )
    ).json()
    assert p2["allocated_amount"] == 200.0
    assert p2["unallocated_amount"] == 150.0

    # Contact statement confirms owed=0, credit_balance=150, net_balance=-150.
    stmt = (
        await client.get(
            f"{_base(owner)}/contacts/{contact.id}/statement",
            params={"as_of": "2026-11-24"},
            headers=h,
        )
    ).json()
    assert len(stmt["balances"]) == 1
    bal = stmt["balances"][0]
    assert bal["currency"] == "UYU"
    assert bal["total_sales"] == 1100.0
    assert bal["paid_total"] == 1250.0
    assert bal["owed_total"] == 0.0
    assert bal["credit_balance"] == 150.0
    assert bal["net_balance"] == -150.0


async def test_manual_allocations_validation_and_multi_currency_isolation(client, db_session):
    owner, h = await _seed(db_session, "-multi")
    stages = await _stages(client, owner, h)
    contact = await _make_contact(db_session, owner, "Carlos")

    s_uyu = await _make_won_sale(
        client,
        owner,
        h,
        stages,
        title="Servicio UYU",
        value=1000,
        currency="UYU",
        contact_id=contact.id,
    )
    s_usd = await _make_won_sale(
        client,
        owner,
        h,
        stages,
        title="Licencia USD",
        value=200,
        currency="USD",
        contact_id=contact.id,
    )

    # Cannot allocate USD payment to UYU sale.
    mismatch = await client.post(
        f"{_base(owner)}/payments",
        json={
            "contact_id": contact.id,
            "amount": 100,
            "currency": "USD",
            "paid_on": "2026-11-20",
            "method": "card",
            "allocation_mode": "manual",
            "allocations": [{"opportunity_id": s_uyu["id"], "amount": 100}],
        },
        headers=h,
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["code"] == "currency_mismatch"

    # Cannot exceed sale owed amount.
    over_sale = await client.post(
        f"{_base(owner)}/payments",
        json={
            "contact_id": contact.id,
            "amount": 300,
            "currency": "USD",
            "paid_on": "2026-11-20",
            "method": "card",
            "allocation_mode": "manual",
            "allocations": [{"opportunity_id": s_usd["id"], "amount": 250}],
        },
        headers=h,
    )
    assert over_sale.status_code == 422
    assert over_sale.json()["code"] == "allocation_exceeds_owed"

    # Cannot exceed payment amount.
    over_pay = await client.post(
        f"{_base(owner)}/payments",
        json={
            "contact_id": contact.id,
            "amount": 50,
            "currency": "USD",
            "paid_on": "2026-11-20",
            "method": "card",
            "allocation_mode": "manual",
            "allocations": [{"opportunity_id": s_usd["id"], "amount": 80}],
        },
        headers=h,
    )
    assert over_pay.status_code == 422
    assert over_pay.json()["code"] == "allocation_exceeds_payment"

    # Partial manual payment in USD + partial in UYU -> separate currency balances!
    assert (
        await client.post(
            f"{_base(owner)}/payments",
            json={
                "contact_id": contact.id,
                "amount": 50,
                "currency": "USD",
                "paid_on": "2026-11-20",
                "method": "card",
                "allocation_mode": "manual",
                "allocations": [{"opportunity_id": s_usd["id"], "amount": 50}],
            },
            headers=h,
        )
    ).status_code == 200
    assert (
        await client.post(
            f"{_base(owner)}/payments",
            json={
                "contact_id": contact.id,
                "amount": 400,
                "currency": "UYU",
                "paid_on": "2026-11-20",
                "method": "cash",
                "allocation_mode": "manual",
                "allocations": [{"opportunity_id": s_uyu["id"], "amount": 250}],
            },
            headers=h,
        )
    ).status_code == 200

    stmt = (await client.get(f"{_base(owner)}/contacts/{contact.id}/statement", headers=h)).json()
    by_cur = {b["currency"]: b for b in stmt["balances"]}
    assert set(by_cur.keys()) == {"USD", "UYU"}
    assert by_cur["USD"]["owed_total"] == 150.0
    assert by_cur["USD"]["credit_balance"] == 0.0
    assert by_cur["UYU"]["owed_total"] == 750.0
    assert by_cur["UYU"]["credit_balance"] == 150.0
    assert by_cur["UYU"]["net_balance"] == 600.0


async def test_overdue_receivables_filters_sorting_summary_and_whatsapp_link(client, db_session):
    owner, h = await _seed(db_session, "-rec")
    agent, _ah = await _agent(db_session, owner, "-rec")
    stages = await _stages(client, owner, h)

    c_overdue = await _make_contact(db_session, owner, "Ana Atrasada", "+59899111222")
    c_upcoming = await _make_contact(db_session, owner, "Bruno Al Día", "+59899333444")

    # Add a WhatsApp inbox + conversation for c_overdue.
    wa_inbox = Inbox(
        account_id=owner.account.id,
        name="WhatsApp Ventas",
        channel_type=CHANNEL_TYPE_WHATSAPP,
        channel_id=1,
    )
    db_session.add(wa_inbox)
    await db_session.flush()
    wa_conv = Conversation(
        account_id=owner.account.id,
        inbox_id=wa_inbox.id,
        contact_id=c_overdue.id,
        status=0,
    )
    db_session.add(wa_conv)
    await db_session.flush()
    await db_session.refresh(wa_conv)

    # c_overdue: credit sale 800 UYU due 2026-11-14 (10 days overdue as of 2026-11-24).
    s1 = await _make_won_sale(
        client,
        owner,
        h,
        stages,
        title="Fiado vencido",
        value=800,
        currency="UYU",
        contact_id=c_overdue.id,
        owner_id=owner.user.id,
    )
    await client.put(
        f"{_base(owner)}/opportunities/{s1['id']}/billing",
        json={"payment_terms": "credit", "due_on": "2026-11-14"},
        headers=h,
    )
    # Partial payment of 200 UYU in Nov -> still owes 600 overdue.
    await client.post(
        f"{_base(owner)}/payments",
        json={
            "contact_id": c_overdue.id,
            "amount": 200,
            "currency": "UYU",
            "paid_on": "2026-11-18",
            "method": "cash",
        },
        headers=h,
    )

    # c_upcoming: installment sale 1000 UYU, first due 2026-12-01 (not overdue).
    s2 = await _make_won_sale(
        client,
        owner,
        h,
        stages,
        title="Cuotas futuras",
        value=1000,
        currency="UYU",
        contact_id=c_upcoming.id,
        owner_id=agent.user.id,
    )
    await client.put(
        f"{_base(owner)}/opportunities/{s2['id']}/billing",
        json={
            "payment_terms": "installments",
            "generate": {"count": 2, "first_due_on": "2026-12-01", "frequency": "monthly"},
        },
        headers=h,
    )

    as_of = "2026-11-24"
    # All receivables.
    all_rec = (
        await client.get(f"{_base(owner)}/receivables", params={"as_of": as_of}, headers=h)
    ).json()
    assert all_rec["meta"]["total"] == 2
    assert all_rec["items"][0]["contact"]["id"] == c_overdue.id
    assert all_rec["items"][0]["days_overdue"] == 10
    assert all_rec["items"][0]["currencies"][0]["overdue_total"] == 600.0
    assert all_rec["items"][0]["whatsapp_conversation"]["display_id"] == wa_conv.display_id

    # Filter overdue only.
    only_overdue = (
        await client.get(
            f"{_base(owner)}/receivables", params={"status": "overdue", "as_of": as_of}, headers=h
        )
    ).json()
    assert [i["contact"]["id"] for i in only_overdue["items"]] == [c_overdue.id]

    # Filter upcoming only.
    only_upcoming = (
        await client.get(
            f"{_base(owner)}/receivables", params={"status": "upcoming", "as_of": as_of}, headers=h
        )
    ).json()
    assert [i["contact"]["id"] for i in only_upcoming["items"]] == [c_upcoming.id]

    # Filter by owner_id.
    by_agent = (
        await client.get(
            f"{_base(owner)}/receivables",
            params={"owner_id": agent.user.id, "as_of": as_of},
            headers=h,
        )
    ).json()
    assert [i["contact"]["id"] for i in by_agent["items"]] == [c_upcoming.id]

    # Summary totals.
    summary = (
        await client.get(f"{_base(owner)}/receivables/summary", params={"as_of": as_of}, headers=h)
    ).json()
    assert summary["debtors_count"] == 2
    assert summary["overdue_debtors_count"] == 1
    [uyu] = summary["currencies"]
    assert uyu["currency"] == "UYU"
    assert uyu["to_collect"] == 1600.0
    assert uyu["overdue"] == 600.0
    assert uyu["collected_this_month"] == 200.0


async def test_payment_permissions_and_created_by(client, db_session):
    owner, h = await _seed(db_session, "-perm")
    agent, ah = await _agent(db_session, owner, "-perm")
    stages = await _stages(client, owner, h)
    contact = await _make_contact(db_session, owner, "Elena")
    await _make_won_sale(
        client, owner, h, stages, title="Venta", value=500, currency="UYU", contact_id=contact.id
    )

    # Agent creates a payment -> created_by is agent.
    created = await client.post(
        f"{_base(owner)}/payments",
        json={
            "contact_id": contact.id,
            "amount": 200,
            "currency": "UYU",
            "paid_on": date.today().isoformat(),
            "method": "cash",
        },
        headers=ah,
    )
    assert created.status_code == 200, created.text
    pay = created.json()
    assert pay["created_by_id"] == agent.user.id
    assert pay["created_by"]["id"] == agent.user.id

    # Agent can edit the payment; created_by stays agent.
    edited = await client.patch(
        f"{_base(owner)}/payments/{pay['id']}",
        json={"note": "Ajustado por agente", "method": "transfer"},
        headers=ah,
    )
    assert edited.status_code == 200
    assert edited.json()["method"] == "transfer"
    assert edited.json()["created_by_id"] == agent.user.id

    # Agent CANNOT delete the payment (401).
    denied = await client.delete(f"{_base(owner)}/payments/{pay['id']}", headers=ah)
    assert denied.status_code == 401

    # Admin CAN delete the payment.
    deleted = await client.delete(f"{_base(owner)}/payments/{pay['id']}", headers=h)
    assert deleted.status_code == 200
    assert (await client.get(f"{_base(owner)}/payments/{pay['id']}", headers=h)).status_code == 404


async def test_changing_or_reopening_paid_sale_requires_explicit_decision(client, db_session):
    owner, h = await _seed(db_session, "-guard")
    stages = await _stages(client, owner, h)
    contact = await _make_contact(db_session, owner, "Diego")
    sale = await _make_won_sale(
        client,
        owner,
        h,
        stages,
        title="Consultoría",
        value=1000,
        currency="UYU",
        contact_id=contact.id,
    )
    pay = (
        await client.post(
            f"{_base(owner)}/payments",
            json={
                "contact_id": contact.id,
                "amount": 600,
                "currency": "UYU",
                "paid_on": "2026-11-20",
                "method": "transfer",
            },
            headers=h,
        )
    ).json()
    assert pay["allocated_amount"] == 600.0

    # Lowering value without decision -> 409, nothing deleted!
    conflict_val = await client.patch(
        f"{_base(owner)}/opportunities/{sale['id']}",
        json={"value": 400},
        headers=h,
    )
    assert conflict_val.status_code == 409
    assert conflict_val.json()["code"] == "opportunity_has_payments"
    assert conflict_val.json()["allocated_amount"] == 600.0
    assert conflict_val.json()["can_keep"] is False

    # Reopening stage without decision -> 409, allocations intact!
    conflict_stage = await client.patch(
        f"{_base(owner)}/opportunities/{sale['id']}",
        json={"stage_id": stages["proposal"]},
        headers=h,
    )
    assert conflict_stage.status_code == 409
    assert conflict_stage.json()["code"] == "opportunity_has_payments"
    assert conflict_stage.json()["reason"] == "stage_change"
    still_paid = (
        await client.get(f"{_base(owner)}/opportunities/{sale['id']}/billing", headers=h)
    ).json()
    assert still_paid["paid_amount"] == 600.0

    # Confirming release_allocations=True moves the sale back to proposal AND turns the 600 payment into credit balance.
    ok_reopen = await client.patch(
        f"{_base(owner)}/opportunities/{sale['id']}",
        json={"stage_id": stages["proposal"], "release_allocations": True},
        headers=h,
    )
    assert ok_reopen.status_code == 200, ok_reopen.text
    assert ok_reopen.json()["payment_terms"] is None
    assert ok_reopen.json()["paid_amount"] == 0.0

    # The payment still exists and is now 100% unallocated (saldo a favor).
    p_after = (await client.get(f"{_base(owner)}/payments/{pay['id']}", headers=h)).json()
    assert p_after["allocated_amount"] == 0.0
    assert p_after["unallocated_amount"] == 600.0

    stmt = (await client.get(f"{_base(owner)}/contacts/{contact.id}/statement", headers=h)).json()
    assert stmt["balances"][0]["credit_balance"] == 600.0
    assert stmt["balances"][0]["net_balance"] == -600.0
