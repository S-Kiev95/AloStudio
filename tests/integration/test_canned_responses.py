"""Integration tests for the CannedResponse CRUD + search surface.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/canned_responses_controller.rb
  reference/chatwoot/app/models/canned_response.rb
    (presence + per-account uniqueness validations, ``order_by_search`` scope)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
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


async def _seed_admin(db_session, suffix: str = ""):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@canned.example.com",
            account_name=f"Canned{suffix}",
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


def _base(account_id: int) -> str:
    return f"/api/v1/accounts/{account_id}/canned_responses"


async def _create(client, base, headers, short_code, content):
    return await client.post(
        base,
        json={"canned_response": {"short_code": short_code, "content": content}},
        headers=headers,
    )


async def test_create_and_index_bare_array(client, db_session):
    owner, headers = await _seed_admin(db_session, "-idx")
    base = _base(owner.account.id)

    r1 = await _create(client, base, headers, "saludo", "Hola!")
    assert r1.status_code == 200, r1.text
    body = r1.json()
    # Bare object (no ``payload`` envelope).
    assert body["short_code"] == "saludo"
    assert body["content"] == "Hola!"
    assert body["account_id"] == owner.account.id

    await _create(client, base, headers, "despedida", "Chau!")

    listing = await client.get(base, headers=headers)
    assert listing.status_code == 200
    rows = listing.json()
    assert isinstance(rows, list)
    assert {r["short_code"] for r in rows} == {"saludo", "despedida"}


async def test_short_code_unique_per_account(client, db_session):
    owner, headers = await _seed_admin(db_session, "-uniq")
    base = _base(owner.account.id)
    assert (await _create(client, base, headers, "dup", "one")).status_code == 200
    clash = await _create(client, base, headers, "dup", "two")
    assert clash.status_code == 422, clash.text
    assert "taken" in clash.json()["message"].lower()


async def test_presence_validations(client, db_session):
    owner, headers = await _seed_admin(db_session, "-pres")
    base = _base(owner.account.id)
    blank_content = await _create(client, base, headers, "code", "   ")
    assert blank_content.status_code == 422
    blank_code = await _create(client, base, headers, "", "body")
    assert blank_code.status_code == 422


async def test_update_and_destroy(client, db_session):
    owner, headers = await _seed_admin(db_session, "-upd")
    base = _base(owner.account.id)
    created = (await _create(client, base, headers, "hi", "Hi")).json()
    cid = created["id"]

    upd = await client.patch(
        f"{base}/{cid}",
        json={"canned_response": {"content": "Hello!"}},
        headers=headers,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["content"] == "Hello!"
    assert upd.json()["short_code"] == "hi"

    dele = await client.delete(f"{base}/{cid}", headers=headers)
    assert dele.status_code == 200
    assert dele.json() == {}
    assert (await client.get(base, headers=headers)).json() == []


async def test_search_ranks_short_code_prefix_first(client, db_session):
    """``?search=`` ranks a short_code *prefix* hit above a short_code
    *substring* hit above a *content* substring hit (Chatwoot's
    ``order_by_search`` CASE)."""
    owner, headers = await _seed_admin(db_session, "-search")
    base = _base(owner.account.id)
    # "gr" — prefix on greet(1.0), substring on angry(0.5),
    # content-only on welcome(0.2).
    await _create(client, base, headers, "greet", "Hello there")
    await _create(client, base, headers, "angry", "Calm down please")
    await _create(client, base, headers, "welcome", "A warm greeting to you")
    # A non-matching row stays out of the results entirely.
    await _create(client, base, headers, "bye", "See you")

    rows = (await client.get(f"{base}?search=gr", headers=headers)).json()
    assert [r["short_code"] for r in rows] == ["greet", "angry", "welcome"]
