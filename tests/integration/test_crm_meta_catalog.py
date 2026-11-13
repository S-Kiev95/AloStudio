"""Products → Meta catalogue (F11). Meta's Graph API is mocked with respx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from decimal import Decimal
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.crm import meta_catalog
from app.domains.products.models import Product
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = r"https://graph\.facebook\.com/v[\d.]+/"


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture(autouse=True)
def _fast_polls(monkeypatch) -> None:
    monkeypatch.setattr(meta_catalog, "STATUS_POLL_SECONDS", 0)


@pytest.fixture
async def seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@catalog.example.com",
            account_name="Colegio CTC",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = tokens
    db_session.add(owner.user)
    await db_session.flush()
    base = f"/api/v1/accounts/{owner.account.id}/crm/meta-catalog"
    return owner.account, headers.as_response_headers(), base


def _product(account_id: int, name: str, **extra) -> Product:
    fields = {
        "description": "Curso de 8 semanas",
        "price": Decimal("4500"),
        "currency": "uyu",
        "url": "https://ctc.example.com/cursos/x",
        "image_url": "https://ctc.example.com/img/x.jpg",
    }
    fields.update(extra)
    return Product(account_id=account_id, name=name, **fields)


@respx.mock
async def test_connecting_checks_the_catalogue_and_keeps_the_token(client, seeded):
    _, headers, base = seeded
    respx.route(host="test").pass_through()
    respx.get(url__regex=GRAPH + r"123456(\?|$)").mock(
        return_value=httpx.Response(200, json={"id": "123456", "name": "Cursos CTC"})
    )
    res = await client.put(
        base, json={"catalog_id": "123456", "access_token": "EAAsecret"}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json() == {
        "connected": True,
        "catalog_id": "123456",
        "catalog_name": "Cursos CTC",
        "last_sync": None,
    }
    assert "EAAsecret" not in res.text

    respx.get(url__regex=GRAPH + r"999(\?|$)").mock(
        return_value=httpx.Response(
            400, json={"error": {"code": 190, "message": "Invalid OAuth access token"}}
        )
    )
    bad = await client.put(
        base, json={"catalog_id": "999", "access_token": "nope"}, headers=headers
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "meta_catalog.token"


@respx.mock
async def test_sync_sends_complete_products_and_says_what_is_missing(
    client, db_session, seeded
):
    account, headers, base = seeded
    respx.route(host="test").pass_through()
    respx.get(url__regex=GRAPH + r"123456(\?|$)").mock(
        return_value=httpx.Response(200, json={"id": "123456", "name": "Cursos CTC"})
    )
    await client.put(base, json={"catalog_id": "123456", "access_token": "EAA"}, headers=headers)

    ready = _product(account.id, "Cerámica", sku="CER-1")
    refused = _product(account.id, "Pintura", sku="PIN-1")
    no_image = _product(account.id, "Dibujo", image_url=None)
    retired = _product(account.id, "Viejo", enabled=False, meta_retailer_id="OLD-1")
    db_session.add_all([ready, refused, no_image, retired])
    await db_session.flush()

    batch = respx.post(url__regex=GRAPH + r"123456/items_batch(\?|$)").mock(
        return_value=httpx.Response(200, json={"handles": ["h1"]})
    )
    respx.get(url__regex=GRAPH + r"123456/check_batch_request_status").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "status": "finished",
                        "errors": [{"id": "PIN-1", "message": "Invalid image"}],
                    }
                ]
            },
        )
    )
    res = await client.post(f"{base}/sync", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["result"] == {"sent": 1, "removed": 1, "skipped": 1, "failed": 1}

    sent = parse_qs(batch.calls.last.request.content.decode())
    assert sent["item_type"] == ["PRODUCT_ITEM"]
    requests = json.loads(sent["requests"][0])
    by_id = {r["data"]["id"]: r for r in requests}
    assert by_id["CER-1"]["method"] == "UPDATE"
    assert by_id["CER-1"]["data"]["price"] == "4500.00 UYU"
    assert by_id["CER-1"]["data"]["brand"] == "Colegio CTC"
    assert by_id["OLD-1"]["method"] == "DELETE"
    assert len(requests) == 3  # the product without an image is not sent

    for p in (ready, refused, no_image, retired):
        await db_session.refresh(p)
    assert ready.meta_synced_at is not None and ready.meta_sync_error is None
    assert refused.meta_sync_error == "Invalid image"
    assert no_image.meta_sync_error == "missing:image_url"
    assert retired.meta_retailer_id is None

    products = await client.get(
        f"/api/v1/accounts/{account.id}/products", headers=headers
    )
    shown = {p["name"]: p for p in products.json()}
    assert shown["Cerámica"]["meta_synced_at"] is not None
    assert shown["Dibujo"]["meta_sync_error"] == "missing:image_url"


@respx.mock
async def test_a_deleted_product_is_removed_on_the_next_sync(client, db_session, seeded):
    account, headers, base = seeded
    respx.route(host="test").pass_through()
    respx.get(url__regex=GRAPH + r"123456(\?|$)").mock(
        return_value=httpx.Response(200, json={"id": "123456", "name": "Cursos CTC"})
    )
    await client.put(base, json={"catalog_id": "123456", "access_token": "EAA"}, headers=headers)
    gone = _product(account.id, "Se va", meta_retailer_id="BYE-1")
    db_session.add(gone)
    await db_session.flush()

    res = await client.delete(
        f"/api/v1/accounts/{account.id}/products/{gone.id}", headers=headers
    )
    assert res.status_code == 200
    hook = await meta_catalog.get_link(db_session, account.id)
    assert hook is not None and hook.settings["pending_removals"] == ["BYE-1"]

    batch = respx.post(url__regex=GRAPH + r"123456/items_batch(\?|$)").mock(
        return_value=httpx.Response(200, json={"handles": []})
    )
    await client.post(f"{base}/sync", headers=headers)
    requests = json.loads(parse_qs(batch.calls.last.request.content.decode())["requests"][0])
    assert requests == [{"method": "DELETE", "data": {"id": "BYE-1"}}]
    await db_session.refresh(hook)
    assert hook.settings["pending_removals"] == []


async def test_sync_without_a_catalogue_says_so(client, seeded):
    _, headers, base = seeded
    res = await client.post(f"{base}/sync", headers=headers)
    assert res.status_code == 422
    assert res.json()["code"] == "meta_catalog.not_connected"
