"""Integration tests for ``/api/v1/accounts/:id/custom_filters``.

Anchor: ``Api::V1::Accounts::CustomFiltersController`` (saved views).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.main import app

pytestmark = pytest.mark.integration

CONV_QUERY = {
    "payload": [
        {
            "attribute_key": "status",
            "filter_operator": "equal_to",
            "values": ["open"],
            "query_operator": "AND",
        }
    ]
}


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
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@cv.example.com",
            account_name="CV Inc",
            user_full_name="CV Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers = await _headers(db_session, owner.user)
    return owner, headers


async def test_create_list_and_delete(client, seeded):
    owner, headers = seeded
    acc = owner.account.id

    created = await client.post(
        f"/api/v1/accounts/{acc}/custom_filters",
        json={
            "name": "Abiertas",
            "filter_type": "conversation",
            "query": CONV_QUERY,
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "Abiertas"
    assert body["filter_type"] == "conversation"
    assert body["query"] == CONV_QUERY
    view_id = body["id"]

    listed = await client.get(
        f"/api/v1/accounts/{acc}/custom_filters?filter_type=conversation",
        headers=headers,
    )
    assert listed.status_code == 200
    assert [v["name"] for v in listed.json()] == ["Abiertas"]

    # filter_type scopes the list — no contact-type views exist.
    contacts = await client.get(
        f"/api/v1/accounts/{acc}/custom_filters?filter_type=contact",
        headers=headers,
    )
    assert contacts.json() == []

    deleted = await client.delete(
        f"/api/v1/accounts/{acc}/custom_filters/{view_id}", headers=headers
    )
    assert deleted.status_code == 200
    after = await client.get(
        f"/api/v1/accounts/{acc}/custom_filters?filter_type=conversation",
        headers=headers,
    )
    assert after.json() == []


async def test_blank_name_rejected(client, seeded):
    owner, headers = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/custom_filters",
        json={"name": "   ", "query": CONV_QUERY},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
