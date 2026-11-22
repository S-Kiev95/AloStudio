"""Connecting the Meta catalogue by logging in with Facebook: one catalogue
connects right away, several wait for the admin's choice, and no token ever
reaches a URL. Meta is mocked with respx."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.crm import meta_catalog, meta_catalog_connect
from app.domains.instagram import oauth
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = oauth._base()
CALLBACK = "/api/v1/instagram/oauth/callback"
BASE_URL = "https://app.example.com"


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


@pytest.fixture
def meta_config():
    settings = get_settings()
    values = {
        "meta_app_id": "APP",
        "meta_app_secret": "SECRET",
        "meta_oauth_redirect_uri": f"{BASE_URL}{CALLBACK}",
        "app_base_url": BASE_URL,
    }
    orig = {name: getattr(settings, name) for name in values}
    for name, value in values.items():
        setattr(settings, name, value)
    try:
        yield settings
    finally:
        for name, value in orig.items():
            setattr(settings, name, value)


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@catlogin.example.com",
            account_name=f"Cat{suffix}",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner.account, headers.as_response_headers()


DATA_ACCESS_UNTIL = 1_803_098_990


def _mock_meta(*businesses: dict, debug: httpx.Response | None = None) -> None:
    respx.get(f"{GRAPH}/oauth/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "USER", "expires_in": 5_184_000})
    )
    # A Business Login token: never expires, its data access does.
    respx.get(f"{GRAPH}/debug_token").mock(
        return_value=debug
        or httpx.Response(
            200,
            json={
                "data": {
                    "is_valid": True,
                    "expires_at": 0,
                    "data_access_expires_at": DATA_ACCESS_UNTIL,
                }
            },
        )
    )
    respx.get(f"{GRAPH}/me/businesses").mock(
        return_value=httpx.Response(200, json={"data": list(businesses)})
    )
    respx.get(url__regex=rf"{GRAPH}/\d+(\?|$)").mock(
        side_effect=lambda request: httpx.Response(
            200, json={"id": request.url.path.rsplit("/", 1)[-1], "name": "Cursos CTC"}
        )
    )


def _state(account_id: int) -> str:
    url = meta_catalog_connect.start_oauth(account_id)
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == ["catalog_management,business_management"]
    return query["state"][0]


def _catalogs(*rows: tuple[str, str]) -> dict:
    return {"data": [{"id": cid, "name": name} for cid, name in rows]}


@respx.mock
async def test_one_catalogue_connects_right_away(client, db_session, meta_config):
    account, headers = await _seed(db_session, "-one")
    respx.route(host="test").pass_through()
    _mock_meta(
        {"id": "9", "name": "CTC Salto", "owned_product_catalogs": _catalogs(("555", "Cursos CTC"))}
    )

    r = await client.get(CALLBACK, params={"code": "C", "state": _state(account.id)})

    assert r.status_code == 303
    assert r.headers["location"] == f"{BASE_URL}/accounts/{account.id}/products?catalog=connected"
    hook = await meta_catalog.get_link(db_session, account.id)
    assert hook is not None and hook.access_token == "USER"
    assert hook.settings["catalog_id"] == "555"
    assert hook.settings["login"]["via"] == "facebook"
    # When the data access ends, not the never-expiring token.
    assert hook.settings["login"]["expires_at"] == DATA_ACCESS_UNTIL

    shown = (
        await client.get(f"/api/v1/accounts/{account.id}/crm/meta-catalog", headers=headers)
    ).json()
    assert shown["can_login"] is True
    assert shown["login"]["via"] == "facebook"
    assert "USER" not in str(shown)


@respx.mock
async def test_several_catalogues_wait_for_the_choice_without_showing_the_token(
    client, db_session, meta_config
):
    account, headers = await _seed(db_session, "-many")
    respx.route(host="test").pass_through()
    _mock_meta(
        {"id": "9", "name": "CTC Salto", "owned_product_catalogs": _catalogs(("555", "Cursos"))},
        {
            "id": "10",
            "name": "Agencia",
            "owned_product_catalogs": _catalogs(("666", "Tienda")),
            # Shared with the agency too: listed once.
            "client_product_catalogs": _catalogs(("555", "Cursos")),
        },
    )

    r = await client.get(CALLBACK, params={"code": "C", "state": _state(account.id)})

    location = urlparse(r.headers["location"])
    assert location.path == f"/accounts/{account.id}/products"
    assert "USER" not in r.headers["location"]
    nonce = parse_qs(location.query)["catalog_pick"][0]
    assert await meta_catalog.get_link(db_session, account.id) is None

    base = f"/api/v1/accounts/{account.id}/crm/meta-catalog"
    listed = await client.get(f"{base}/pending/{nonce}", headers=headers)
    assert listed.status_code == 200
    assert listed.json() == [
        {"id": "555", "name": "Cursos", "business": "CTC Salto"},
        {"id": "666", "name": "Tienda", "business": "Agencia"},
    ]
    assert "USER" not in listed.text

    foreign = await client.post(f"{base}/pending/{nonce}/777", headers=headers)
    assert foreign.status_code == 422
    assert foreign.json()["code"] == "meta_catalog.catalog_id"

    chosen = await client.post(f"{base}/pending/{nonce}/666", headers=headers)
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["catalog_id"] == "666"
    gone = await client.get(f"{base}/pending/{nonce}", headers=headers)
    assert gone.json()["code"] == "meta_catalog.pick_expired"


@respx.mock
async def test_cancelling_or_having_no_catalogue_comes_back_with_a_code(
    client, db_session, meta_config
):
    account, _ = await _seed(db_session, "-none")
    respx.route(host="test").pass_through()
    state = _state(account.id)

    r = await client.get(CALLBACK, params={"error": "access_denied", "state": state})
    assert r.headers["location"].endswith("/products?catalog_error=cancelled")

    _mock_meta({"id": "9", "name": "Sin catálogos"})
    r = await client.get(CALLBACK, params={"code": "C", "state": state})
    assert r.headers["location"].endswith("/products?catalog_error=no_catalogs")


async def test_without_the_meta_app_the_button_is_not_offered(client, db_session, meta_config):
    account, headers = await _seed(db_session, "-off")
    meta_config.meta_app_secret = ""
    shown = await client.get(f"/api/v1/accounts/{account.id}/crm/meta-catalog", headers=headers)
    assert shown.json() == {"connected": False, "can_login": False}
    start = await client.get(
        f"/api/v1/accounts/{account.id}/crm/meta-catalog/connect/start", headers=headers
    )
    assert start.status_code == 422
    assert start.json()["code"] == "meta_catalog.login_unavailable"


@respx.mock
async def test_without_debug_token_the_expiry_comes_from_the_exchange(
    client, db_session, meta_config
):
    account, _ = await _seed(db_session, "-nodebug")
    respx.route(host="test").pass_through()
    _mock_meta(
        {"id": "9", "name": "CTC Salto", "owned_product_catalogs": _catalogs(("555", "Cursos"))},
        debug=httpx.Response(400, json={"error": {"code": 100, "message": "nope"}}),
    )
    await client.get(CALLBACK, params={"code": "C", "state": _state(account.id)})
    hook = await meta_catalog.get_link(db_session, account.id)
    assert hook is not None
    expires_at = hook.settings["login"]["expires_at"]
    # expires_in of the long-lived exchange (60 days) from now.
    assert 5_000_000 < expires_at - time.time() < 5_200_000


@respx.mock
async def test_a_business_configuration_gets_a_token_that_does_not_expire(
    client, db_session, meta_config
):
    """With META_CATALOG_CONFIG_ID the login hands over the business's
    system-user token: no long-lived exchange, catalogues of that business
    only, and nothing to expire."""
    account, _ = await _seed(db_session, "-biz")
    respx.route(host="test").pass_through()
    meta_config.meta_catalog_config_id = "CFG-CAT"
    try:
        url = meta_catalog_connect.start_oauth(account.id)
        query = parse_qs(urlparse(url).query)
        assert query["config_id"] == ["CFG-CAT"]
        assert "scope" not in query
        exchange = respx.get(f"{GRAPH}/oauth/access_token").mock(
            return_value=httpx.Response(200, json={"access_token": "BISU"})
        )
        respx.get(f"{GRAPH}/debug_token").mock(
            return_value=httpx.Response(
                200, json={"data": {"is_valid": True, "expires_at": 0, "data_access_expires_at": 0}}
            )
        )
        # Through the business (owned_product_catalogs) Meta answers 403
        # to a system-user token; its assigned catalogues are the way.
        respx.get(f"{GRAPH}/me/assigned_product_catalogs").mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "555", "name": "Cursos", "business": {"name": "CTC"}}]}
            )
        )
        respx.get(url__regex=rf"{GRAPH}/555(\?|$)").mock(
            return_value=httpx.Response(200, json={"id": "555", "name": "Cursos"})
        )
        r = await client.get(CALLBACK, params={"code": "C", "state": query["state"][0]})
    finally:
        meta_config.meta_catalog_config_id = ""

    assert r.headers["location"].endswith("/products?catalog=connected")
    assert exchange.call_count == 1
    hook = await meta_catalog.get_link(db_session, account.id)
    assert hook is not None and hook.access_token == "BISU"
    assert hook.settings["catalog_id"] == "555"
    assert hook.settings["login"] == {"via": "facebook_business", "expires_at": None}
