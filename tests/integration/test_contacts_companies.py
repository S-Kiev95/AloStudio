"""Integration tests for the contact "companies" roll-up + ``?company=`` filter.

Chatwoot has no Company model — an organisation is the free-text
``additional_attributes['company_name']`` contact attribute. These cover
the derived aggregation (``GET /contacts/companies``) and the list filter
(``GET /contacts?company=``).
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


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@co.example.com",
            account_name=f"CO{suffix}",
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


async def _new_contact(client, account_id, headers, name, company=None):
    body: dict = {"name": name}
    if company is not None:
        body["additional_attributes"] = {"company_name": company}
    resp = await client.post(
        f"/api/v1/accounts/{account_id}/contacts", json=body, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return resp


async def test_companies_rollup_and_filter(client, db_session):
    owner, headers = await _seed_admin(db_session, "-roll")
    aid = owner.account.id
    await _new_contact(client, aid, headers, "A1", "Acme")
    await _new_contact(client, aid, headers, "A2", "Acme")
    await _new_contact(client, aid, headers, "G1", "Globex")
    await _new_contact(client, aid, headers, "N1")  # no company — excluded
    await _new_contact(client, aid, headers, "B1", "")  # blank — excluded

    # Roll-up: ordered by count desc, blanks/nulls dropped.
    companies = (
        await client.get(
            f"/api/v1/accounts/{aid}/contacts/companies", headers=headers
        )
    ).json()
    assert companies == [
        {"name": "Acme", "count": 2},
        {"name": "Globex", "count": 1},
    ]

    # Drill-down: ?company= narrows the list.
    filtered = (
        await client.get(
            f"/api/v1/accounts/{aid}/contacts?company=Acme", headers=headers
        )
    ).json()
    names = sorted(c["name"] for c in filtered["payload"])
    assert names == ["A1", "A2"]
    assert filtered["meta"]["count"] == 2


async def test_companies_empty_account(client, db_session):
    owner, headers = await _seed_admin(db_session, "-empty")
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/contacts/companies",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []
