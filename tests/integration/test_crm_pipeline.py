"""Sales pipeline (F11): pipelines, stages and opportunities."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
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
            email=f"admin{suffix}@crm.example.com",
            account_name=f"CRM{suffix}",
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
            email=f"agent{suffix}@crm.example.com",
            account_name=f"CRMA{suffix}",
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


async def _stages(client, owner, headers) -> dict[str, int]:
    resp = await client.get(f"{_base(owner)}/pipelines", headers=headers)
    assert resp.status_code == 200, resp.text
    return {s["code"]: s["id"] for s in resp.json()[0]["stages"]}


async def test_an_account_starts_with_the_default_pipeline(client, db_session):
    owner, h = await _seed(db_session, "-default")
    resp = await client.get(f"{_base(owner)}/pipelines", headers=h)
    assert resp.status_code == 200
    [pipeline] = resp.json()
    assert pipeline["is_default"] is True and pipeline["name"] is None
    assert [s["code"] for s in pipeline["stages"]] == [
        "new",
        "qualified",
        "proposal",
        "negotiation",
        "won",
        "lost",
    ]
    assert [s["kind"] for s in pipeline["stages"]][-2:] == ["won", "lost"]
    # Asking again doesn't create a second one.
    assert len((await client.get(f"{_base(owner)}/pipelines", headers=h)).json()) == 1


async def test_opportunity_lifecycle(client, db_session):
    owner, h = await _seed(db_session, "-life")
    stages = await _stages(client, owner, h)
    contact = Contact(account_id=owner.account.id, name="Lucía")
    db_session.add(contact)
    await db_session.flush()

    created = await client.post(
        f"{_base(owner)}/opportunities",
        json={
            "title": "Curso de inglés",
            "value": 1200.5,
            "currency": "UYU",
            "contact_id": contact.id,
            "expected_close_on": "2026-12-01",
        },
        headers=h,
    )
    assert created.status_code == 200, created.text
    opp = created.json()
    # No stage given: the first stage of the default pipeline; owned by its creator.
    assert opp["stage_id"] == stages["new"]
    assert opp["owner_id"] == owner.user.id
    assert opp["contact"]["name"] == "Lucía"
    assert opp["value"] == 1200.5 and opp["expected_close_on"] == "2026-12-01"
    assert opp["closed_at"] is None

    won = await client.patch(
        f"{_base(owner)}/opportunities/{opp['id']}", json={"stage_id": stages["won"]}, headers=h
    )
    assert won.status_code == 200
    assert won.json()["closed_at"] is not None

    reopened = await client.patch(
        f"{_base(owner)}/opportunities/{opp['id']}",
        json={"stage_id": stages["proposal"]},
        headers=h,
    )
    assert reopened.json()["closed_at"] is None

    listed = await client.get(
        f"{_base(owner)}/opportunities", params={"contact_id": contact.id}, headers=h
    )
    assert [o["id"] for o in listed.json()] == [opp["id"]]
    assert (
        await client.get(f"{_base(owner)}/opportunities", params={"status": "won"}, headers=h)
    ).json() == []

    assert (
        await client.delete(f"{_base(owner)}/opportunities/{opp['id']}", headers=h)
    ).status_code == 200
    assert (
        await client.get(f"{_base(owner)}/opportunities/{opp['id']}", headers=h)
    ).status_code == 404


async def test_title_is_required_and_references_stay_in_the_account(client, db_session):
    owner, h = await _seed(db_session, "-refs")
    other, _ = await _seed(db_session, "-refs-other")
    foreign = Contact(account_id=other.account.id, name="Ajeno")
    db_session.add(foreign)
    await db_session.flush()
    other_stages = await _stages(client, other, await _headers(db_session, other.user))

    blank = await client.post(f"{_base(owner)}/opportunities", json={"title": " "}, headers=h)
    assert blank.status_code == 422
    assert blank.json()["code"] == "blank"

    for body in (
        {"title": "X", "contact_id": foreign.id},
        {"title": "X", "stage_id": other_stages["new"]},
        {"title": "X", "owner_id": other.user.id},
    ):
        resp = await client.post(f"{_base(owner)}/opportunities", json=body, headers=h)
        assert resp.status_code == 422, body


async def test_agents_sell_but_only_admins_shape_the_pipeline(client, db_session):
    owner, h = await _seed(db_session, "-roles")
    _agent_user, ah = await _agent(db_session, owner, "-roles")
    stages = await _stages(client, owner, h)

    assert (
        await client.post(
            f"{_base(owner)}/opportunities", json={"title": "Venta"}, headers=ah
        )
    ).status_code == 200
    pipeline_id = (await client.get(f"{_base(owner)}/pipelines", headers=ah)).json()[0]["id"]
    resp = await client.patch(
        f"{_base(owner)}/pipelines/{pipeline_id}", json={"rotten_days": 10}, headers=ah
    )
    assert resp.status_code == 401
    assert stages  # admin sees the same pipeline


async def test_editing_stages(client, db_session):
    owner, h = await _seed(db_session, "-stages")
    [pipeline] = (await client.get(f"{_base(owner)}/pipelines", headers=h)).json()
    keep = [s for s in pipeline["stages"] if s["code"] in ("new", "won", "lost")]
    body = {
        "rotten_days": 14,
        "stages": [
            {"id": keep[0]["id"], "kind": "open", "probability": 20},
            {"name": "Demo agendada", "kind": "open", "probability": 60},
            {"id": keep[1]["id"], "kind": "won", "probability": 100},
            {"id": keep[2]["id"], "kind": "lost", "probability": 0},
        ],
    }
    resp = await client.patch(f"{_base(owner)}/pipelines/{pipeline['id']}", json=body, headers=h)
    assert resp.status_code == 200, resp.text
    edited = resp.json()
    assert edited["rotten_days"] == 14
    assert [(s["code"], s["name"]) for s in edited["stages"]] == [
        ("new", None),
        (None, "Demo agendada"),
        ("won", None),
        ("lost", None),
    ]

    # A stage still holding an opportunity can't be dropped.
    await client.post(
        f"{_base(owner)}/opportunities",
        json={"title": "En demo", "stage_id": edited["stages"][1]["id"]},
        headers=h,
    )
    body["stages"] = [s for s in body["stages"] if s.get("name") != "Demo agendada"]
    resp = await client.patch(f"{_base(owner)}/pipelines/{pipeline['id']}", json=body, headers=h)
    assert resp.status_code == 422

    # And a pipeline needs at least one open stage.
    resp = await client.patch(
        f"{_base(owner)}/pipelines/{pipeline['id']}",
        json={"stages": [{"id": keep[1]["id"], "kind": "won", "probability": 100}]},
        headers=h,
    )
    assert resp.status_code == 422


async def test_new_pipeline_and_default_cannot_be_deleted(client, db_session):
    owner, h = await _seed(db_session, "-pipes")
    [default] = (await client.get(f"{_base(owner)}/pipelines", headers=h)).json()
    created = await client.post(f"{_base(owner)}/pipelines", json={"name": "Escuela"}, headers=h)
    assert created.status_code == 200
    assert len(created.json()["stages"]) == 6
    assert (
        await client.delete(f"{_base(owner)}/pipelines/{default['id']}", headers=h)
    ).status_code == 422
    assert (
        await client.delete(f"{_base(owner)}/pipelines/{created.json()['id']}", headers=h)
    ).status_code == 200
