"""Integration tests for the contact filter-DSL (``POST /contacts/filter``).

Backs contact *segments* (a saved contact filter). Same condition shape as
the conversation filter, over contact attributes.
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
            email=f"admin{suffix}@cf.example.com",
            account_name=f"CF{suffix}",
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


async def _seed_contacts(client, account_id, headers):
    payloads = [
        {"name": "Ana", "email": "ana@acme.com",
         "additional_attributes": {"company_name": "Acme"}},
        {"name": "Beto", "email": "beto@globex.com",
         "additional_attributes": {"company_name": "Globex"}},
        {"name": "Caro", "phone_number": "+59899111",
         "additional_attributes": {"company_name": "Acme"}},
    ]
    for p in payloads:
        r = await client.post(
            f"/api/v1/accounts/{account_id}/contacts", json=p, headers=headers
        )
        assert r.status_code == 200, r.text


async def _filter(client, account_id, headers, payload):
    resp = await client.post(
        f"/api/v1/accounts/{account_id}/contacts/filter",
        json={"payload": payload},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return sorted(c["name"] for c in body["payload"]), body["meta"]["count"]


async def test_contact_filter_by_attributes(client, db_session):
    owner, headers = await _seed_admin(db_session, "-attr")
    aid = owner.account.id
    await _seed_contacts(client, aid, headers)

    # Text equal_to is case-insensitive.
    names, count = await _filter(
        client, aid, headers,
        [{"attribute_key": "name", "filter_operator": "equal_to",
          "values": ["ana"]}],
    )
    assert names == ["Ana"] and count == 1

    # company_name contains (JSONB, case-insensitive) → Acme members.
    names, _ = await _filter(
        client, aid, headers,
        [{"attribute_key": "company_name", "filter_operator": "contains",
          "values": ["acm"]}],
    )
    assert names == ["Ana", "Caro"]

    # is_not_present on email → the phone-only contact.
    names, _ = await _filter(
        client, aid, headers,
        [{"attribute_key": "email", "filter_operator": "is_not_present",
          "values": []}],
    )
    assert names == ["Caro"]

    # AND combo: Acme company + has an email → only Ana.
    names, _ = await _filter(
        client, aid, headers,
        [
            {"attribute_key": "company_name", "filter_operator": "equal_to",
             "values": ["Acme"], "query_operator": "AND"},
            {"attribute_key": "email", "filter_operator": "is_present",
             "values": []},
        ],
    )
    assert names == ["Ana"]

    # OR combo: name is Ana OR company is Globex → Ana + Beto.
    names, _ = await _filter(
        client, aid, headers,
        [
            {"attribute_key": "name", "filter_operator": "equal_to",
             "values": ["Ana"], "query_operator": "OR"},
            {"attribute_key": "company_name", "filter_operator": "equal_to",
             "values": ["Globex"]},
        ],
    )
    assert names == ["Ana", "Beto"]


async def test_contact_filter_rejects_bad_payload(client, db_session):
    owner, headers = await _seed_admin(db_session, "-bad")
    aid = owner.account.id
    # Missing payload key.
    r1 = await client.post(
        f"/api/v1/accounts/{aid}/contacts/filter", json={}, headers=headers
    )
    assert r1.status_code == 400
    # Unknown attribute.
    r2 = await client.post(
        f"/api/v1/accounts/{aid}/contacts/filter",
        json={"payload": [{"attribute_key": "nope",
                           "filter_operator": "equal_to", "values": ["x"]}]},
        headers=headers,
    )
    assert r2.status_code == 400
