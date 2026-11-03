"""Sign in with Google: only invited users get in, from the browser that
started it, with a verified address of the allowed domain. Google is
mocked with respx."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.db import get_session
from app.core.oauth_state import sign_oauth_state
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.auth.google import TOKEN_URL
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

NONCE = "n" * 32


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
def google_config():
    settings = get_settings()
    names = ("google_client_id", "google_client_secret", "google_allowed_domain", "app_base_url")
    orig = {name: getattr(settings, name) for name in names}
    settings.google_client_id = "GID.apps.googleusercontent.com"
    settings.google_client_secret = "GSECRET"
    settings.google_allowed_domain = "escuela.edu.uy"
    settings.app_base_url = "https://app.example.com"
    try:
        yield settings
    finally:
        for name, value in orig.items():
            setattr(settings, name, value)


def _id_token(**claims) -> str:
    body = {
        "iss": "https://accounts.google.com",
        "aud": "GID.apps.googleusercontent.com",
        "exp": int(time.time()) + 600,
        "email_verified": True,
        "hd": "escuela.edu.uy",
        **claims,
    }

    def part(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'RS256'})}.{part(body)}.firma"


def _google_answers(**claims) -> respx.Route:
    return respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"id_token": _id_token(**claims), "access_token": "x"})
    )


async def _invited(db_session, email: str, *, confirmed: bool = True):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=email,
            account_name="CTC",
            user_full_name="Docente",
            user_password="Password123!",
            confirmed=confirmed,
        ),
    ).perform()


def _sign_in(client: AsyncClient, *, nonce: str = NONCE, state_nonce: str = NONCE):
    state = sign_oauth_state(0, flow=f"google_login:{state_nonce}")
    return client.post("/auth/google", json={"code": "CODE", "state": state, "nonce": nonce})


async def test_the_button_shows_only_when_configured(client, google_config):
    google_config.google_client_secret = ""
    assert (await client.get("/auth/google")).json() == {"enabled": False}
    assert (await client.get("/auth/google/authorize_url", params={"nonce": NONCE})).status_code == 404

    google_config.google_client_secret = "GSECRET"
    assert (await client.get("/auth/google")).json() == {"enabled": True}
    r = await client.get("/auth/google/authorize_url", params={"nonce": NONCE})
    query = parse_qs(urlparse(r.json()["url"]).query)
    assert query["client_id"] == ["GID.apps.googleusercontent.com"]
    assert query["redirect_uri"] == ["https://app.example.com/auth/google/callback"]
    assert query["scope"] == ["openid email profile"]
    assert query["hd"] == ["escuela.edu.uy"]


@respx.mock
async def test_an_invited_user_signs_in(client, db_session, google_config):
    owner = await _invited(db_session, "docente@escuela.edu.uy", confirmed=False)
    token = _google_answers(email="Docente@Escuela.edu.uy")

    r = await _sign_in(client)

    assert r.status_code == 200, r.text
    assert r.headers["access-token"] and r.headers["uid"] == "docente@escuela.edu.uy"
    assert r.json()["data"]["account_id"] == owner.account.id
    sent = parse_qs(token.calls[0].request.content.decode())
    assert sent["client_secret"] == ["GSECRET"]
    assert sent["redirect_uri"] == ["https://app.example.com/auth/google/callback"]
    # Google proved the address: the pending invitation counts as confirmed.
    await db_session.refresh(owner.user)
    assert owner.user.confirmed_at is not None


@respx.mock
async def test_who_does_not_get_in(client, db_session, google_config):
    await _invited(db_session, "docente2@escuela.edu.uy")

    # Not invited.
    _google_answers(email="otro@escuela.edu.uy")
    r = await _sign_in(client)
    assert r.status_code == 403
    assert "Pedile a un administrador" in r.json()["errors"][0]

    # Another browser: the nonce in the state isn't this one.
    _google_answers(email="docente2@escuela.edu.uy")
    assert (await _sign_in(client, nonce="x" * 32)).status_code == 401

    # Outside the allowed domain, unverified address, or a token for another app.
    _google_answers(email="docente2@escuela.edu.uy", hd="gmail.com")
    assert (await _sign_in(client)).status_code == 401
    _google_answers(email="docente2@escuela.edu.uy", email_verified=False)
    assert (await _sign_in(client)).status_code == 401
    _google_answers(email="docente2@escuela.edu.uy", aud="otra-app")
    assert (await _sign_in(client)).status_code == 401

    # Google refusing the code.
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    assert (await _sign_in(client)).status_code == 401
