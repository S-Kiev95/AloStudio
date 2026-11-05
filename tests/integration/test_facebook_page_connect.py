"""Connecting a Facebook Page by logging in with Facebook: one Page connects
right away, several wait for the admin's choice, and a reconnect keeps the
inbox. Meta is mocked with respx."""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.facebook import connect_service
from app.domains.inboxes.models import FacebookPage, Inbox
from app.domains.instagram import oauth
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
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
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
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
            email=f"admin{suffix}@fbpage.example.com",
            account_name=f"FB{suffix}",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


def _mock_meta(*pages: dict) -> respx.Route:
    respx.get(f"{GRAPH}/oauth/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "USER"})
    )
    respx.get(f"{GRAPH}/me/accounts").mock(return_value=httpx.Response(200, json={"data": list(pages)}))
    return respx.post(url__regex=rf"{GRAPH}/\d+/subscribed_apps").mock(
        return_value=httpx.Response(200, json={"success": True})
    )


def _state(client_account: int) -> str:
    url = connect_service.start_page_oauth(client_account)
    query = parse_qs(urlparse(url).query)
    assert "pages_manage_posts" in query["scope"][0]
    assert "read_insights" in query["scope"][0]
    return query["state"][0]


@respx.mock
async def test_one_page_connects_and_reconnecting_keeps_the_inbox(client, db_session, meta_config):
    owner, _h = await _seed(db_session, "-one")
    subscribe = _mock_meta({"id": "111", "name": "Instituto", "access_token": "PAGE"})
    state = _state(owner.account.id)

    r = await client.get(CALLBACK, params={"code": "C", "state": state})

    assert r.status_code == 303
    page = (await db_session.exec(select(FacebookPage).where(FacebookPage.page_id == "111"))).one()
    inbox = (await db_session.exec(select(Inbox).where(Inbox.channel_id == page.id, Inbox.channel_type == "Channel::FacebookPage"))).one()
    assert inbox.name == "Instituto"
    assert r.headers["location"] == f"{BASE_URL}/accounts/{owner.account.id}/settings/inboxes/{inbox.id}"
    assert page.page_access_token == "PAGE"
    assert subscribe.call_count == 1

    _mock_meta({"id": "111", "name": "Instituto", "access_token": "PAGE2"})
    r = await client.get(CALLBACK, params={"code": "C", "state": state})
    assert r.headers["location"].endswith(f"/inboxes/{inbox.id}")
    await db_session.refresh(page)
    assert page.page_access_token == "PAGE2"


@respx.mock
async def test_several_pages_wait_for_the_choice_without_showing_tokens(client, db_session, meta_config):
    owner, h = await _seed(db_session, "-many")
    _mock_meta(
        {"id": "221", "name": "Instituto", "access_token": "PAGE1"},
        {"id": "222", "name": "Alianza", "access_token": "PAGE2"},
    )

    r = await client.get(CALLBACK, params={"code": "C", "state": _state(owner.account.id)})

    assert r.status_code == 303
    location = urlparse(r.headers["location"])
    assert location.path.endswith("/settings/inboxes/new/facebook")
    assert "PAGE" not in r.headers["location"]
    nonce = parse_qs(location.query)["fb_pick"][0]
    base = f"/api/v1/accounts/{owner.account.id}/facebook_pages/pending/{nonce}"

    r = await client.get(base, headers=h)
    assert r.json() == [{"id": "221", "name": "Instituto"}, {"id": "222", "name": "Alianza"}]

    assert (await client.post(f"{base}/999", headers=h)).status_code == 422

    r = await client.post(f"{base}/222", headers=h)
    assert r.status_code == 200, r.text
    page = (await db_session.exec(select(FacebookPage).where(FacebookPage.page_id == "222"))).one()
    assert page.page_access_token == "PAGE2"
    assert (await db_session.exec(select(FacebookPage).where(FacebookPage.page_id == "221"))).first() is None

    # The choice is used up.
    assert (await client.get(base, headers=h)).status_code == 422


@respx.mock
async def test_a_page_of_another_account_is_refused(client, db_session, meta_config):
    first, _h = await _seed(db_session, "-a")
    second, _h = await _seed(db_session, "-b")
    _mock_meta({"id": "331", "name": "Instituto", "access_token": "PAGE"})
    await client.get(CALLBACK, params={"code": "C", "state": _state(first.account.id)})

    r = await client.get(CALLBACK, params={"code": "C", "state": _state(second.account.id)})

    assert "fb_error" in r.headers["location"]
    page = (await db_session.exec(select(FacebookPage).where(FacebookPage.page_id == "331"))).one()
    assert page.account_id == first.account.id


async def test_a_cancelled_login_goes_back_to_the_form(client, db_session, meta_config):
    owner, _h = await _seed(db_session, "-no")
    state = _state(owner.account.id)
    r = await client.get(CALLBACK, params={"error": "access_denied", "state": state})
    assert r.status_code == 303
    assert "/settings/inboxes/new/facebook?fb_error=" in r.headers["location"]


async def test_start_asks_for_the_settings_it_needs(client, db_session, meta_config):
    owner, h = await _seed(db_session, "-cfg")
    meta_config.meta_app_secret = ""
    r = await client.get(f"/api/v1/accounts/{owner.account.id}/facebook_pages/connect/start", headers=h)
    assert r.status_code == 422 and "META_APP_SECRET" in r.json()["message"]
