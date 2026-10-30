"""OAuth apps: AloStudio as an OAuth 2.0 authorization server whose tokens
work on the MCP server."""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.oauth.models import OAuthAuthorizationCode
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_AGENT,
    AccountUser,
)
from app.main import app
from app.mcp.service import MCPAuthError, resolve_token

pytestmark = pytest.mark.integration

CALLBACK = "https://example.com/oauth/callback"


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


async def _auth(db_session, user) -> dict[str, str]:
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@oauth.example.com",
            account_name=f"OAU{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    return owner, await _auth(db_session, owner.user)


async def _seed_agent(db_session, account_id: int, suffix: str):
    other = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@oauth.example.com",
            account_name=f"OAUAGENT{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(account_id=account_id, user_id=other.user.id, role=ACCOUNT_USER_ROLE_AGENT)
    )
    await db_session.flush()
    return other, await _auth(db_session, other.user)


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def _create_app(client, account_id: int, h, *, confidential: bool = True) -> dict:
    r = await client.post(
        f"/api/v1/accounts/{account_id}/oauth_apps",
        headers=h,
        json={"name": "Mi integración", "redirect_uris": [CALLBACK], "confidential": confidential},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _authorize_params(app_json: dict, challenge: str | None, *, scope: str = "write") -> dict:
    params = {
        "response_type": "code",
        "client_id": app_json["client_id"],
        "redirect_uri": CALLBACK,
        "scope": scope,
        "state": "xyz",
    }
    if challenge:
        params |= {"code_challenge": challenge, "code_challenge_method": "S256"}
    return params


async def _code(client, h, app_json: dict, account_id: int, challenge: str | None, **kw) -> str:
    r = await client.post(
        "/api/v1/oauth/authorize",
        headers=h,
        json=_authorize_params(app_json, challenge, **kw) | {"account_id": account_id, "approve": True},
    )
    assert r.status_code == 200, r.text
    query = parse_qs(urlsplit(r.json()["redirect_to"]).query)
    assert query["state"] == ["xyz"]
    return query["code"][0]


async def _token(client, app_json: dict, **form) -> dict:
    r = await client.post(
        "/oauth/token", data=form, auth=(app_json["client_id"], app_json["client_secret"])
    )
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()


async def _resolves(db_session, token: str):
    try:
        return await resolve_token(db_session, token_value=token)
    except MCPAuthError:
        return None


# ---------------------------------------------------------------------------
async def test_apps_crud_and_the_secret_shown_once(client, db_session):
    owner, h = await _seed(db_session, "-crud")
    _, agent_h = await _seed_agent(db_session, owner.account.id, "-crud")
    base = f"/api/v1/accounts/{owner.account.id}/oauth_apps"

    created = await _create_app(client, owner.account.id, h)
    assert created["client_id"].startswith("alo_app_")
    assert created["client_secret"].startswith("alo_secret_")
    assert (created["confidential"], created["redirect_uris"], created["authorizations_count"]) == (
        True,
        [CALLBACK],
        0,
    )

    listing = (await client.get(base, headers=h)).json()
    assert ["client_secret" in a for a in listing["apps"]] == [False]
    base_url = get_settings().app_base_url.rstrip("/")
    assert listing["endpoints"] == {
        "authorization": f"{base_url}/oauth/authorize",
        "token": f"{base_url}/oauth/token",
        "revocation": f"{base_url}/oauth/revoke",
        "metadata": f"{base_url}/.well-known/oauth-authorization-server",
        "mcp": f"{base_url}/mcp",
    }

    r = await client.patch(
        f"{base}/{created['id']}",
        headers=h,
        json={"name": "  Otra   integración ", "redirect_uris": [CALLBACK, "http://localhost:3000/cb"]},
    )
    assert (r.json()["name"], r.json()["redirect_uris"]) == (
        "Otra integración",
        [CALLBACK, "http://localhost:3000/cb"],
    )
    rotated = (await client.post(f"{base}/{created['id']}/secret", headers=h)).json()
    assert rotated["client_secret"] != created["client_secret"]

    for payload in (
        {"name": "x", "redirect_uris": ["http://example.com/cb"]},
        {"name": "x", "redirect_uris": ["https://example.com/cb#frag"]},
        {"name": "   ", "redirect_uris": [CALLBACK]},
        {"name": "x", "redirect_uris": []},
        {"name": "x", "redirect_uris": [f"https://example.com/{i}" for i in range(11)]},
    ):
        r = await client.post(base, headers=h, json=payload)
        assert r.status_code == 422, payload
        assert r.json()["message"]

    public = await _create_app(client, owner.account.id, h, confidential=False)
    assert "client_secret" not in public and public["confidential"] is False
    assert (await client.post(f"{base}/{public['id']}/secret", headers=h)).status_code == 422

    # Only administrators manage apps.
    assert (await client.get(base, headers=agent_h)).status_code == 401

    assert (await client.delete(f"{base}/{created['id']}", headers=h)).status_code == 200
    assert [a["id"] for a in (await client.get(base, headers=h)).json()["apps"]] == [public["id"]]


async def test_the_code_flow_with_pkce_refresh_and_revocation(client, db_session):
    owner, h = await _seed(db_session, "-flow")
    app_json = await _create_app(client, owner.account.id, h)
    verifier, challenge = _pkce()

    preview = (
        await client.get(
            "/api/v1/oauth/authorize", headers=h, params=_authorize_params(app_json, challenge)
        )
    ).json()
    assert preview["app"] == {
        "name": "Mi integración",
        "client_id": app_json["client_id"],
        "owner_account_name": owner.account.name,
    }
    assert (preview["scope"], preview["redirect_uri"]) == ("write", CALLBACK)
    assert preview["accounts"] == [
        {"id": owner.account.id, "name": owner.account.name, "role": "administrator", "can_grant": True}
    ]

    code = await _code(client, h, app_json, owner.account.id, challenge)
    tokens = await _token(
        client,
        app_json,
        grant_type="authorization_code",
        code=code,
        redirect_uri=CALLBACK,
        code_verifier=verifier,
    )
    assert tokens["access_token"].startswith("alo_at_")
    assert tokens["refresh_token"].startswith("alo_rt_")
    assert (tokens["token_type"], tokens["expires_in"], tokens["scope"]) == ("Bearer", 3600, "write")

    # The token works on the MCP server, as the user who authorized it.
    ctx = await _resolves(db_session, tokens["access_token"])
    assert (ctx.account.id, ctx.user.id, ctx.scope) == (owner.account.id, owner.user.id, "write")
    approved = (
        await client.get(f"/api/v1/accounts/{owner.account.id}/oauth_authorizations", headers=h)
    ).json()["authorizations"]
    assert [(a["app"]["name"], a["scope"]) for a in approved] == [("Mi integración", "write")]
    assert approved[0]["last_used_at"] is not None
    listing = (await client.get(f"/api/v1/accounts/{owner.account.id}/oauth_apps", headers=h)).json()
    assert listing["apps"][0]["authorizations_count"] == 1

    # Refresh rotates: the old pair stops working, a replay kills the family.
    renewed = await _token(
        client, app_json, grant_type="refresh_token", refresh_token=tokens["refresh_token"]
    )
    assert await _resolves(db_session, tokens["access_token"]) is None
    assert (await _resolves(db_session, renewed["access_token"])).scope == "write"
    replay = await client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]},
        auth=(app_json["client_id"], app_json["client_secret"]),
    )
    assert (replay.status_code, replay.json()["error"]) == (400, "invalid_grant")
    assert await _resolves(db_session, renewed["access_token"]) is None

    # A new grant, revoked from "Apps aprobadas".
    verifier, challenge = _pkce()
    code = await _code(client, h, app_json, owner.account.id, challenge)
    fresh = await _token(
        client, app_json, grant_type="authorization_code", code=code, code_verifier=verifier
    )
    r = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/oauth_authorizations/{app_json['id']}", headers=h
    )
    assert r.status_code == 200
    assert await _resolves(db_session, fresh["access_token"]) is None
    assert (
        await client.get(f"/api/v1/accounts/{owner.account.id}/oauth_authorizations", headers=h)
    ).json() == {"authorizations": []}


async def test_codes_are_single_use_short_lived_and_bound(client, db_session):
    owner, h = await _seed(db_session, "-code")
    app_json = await _create_app(client, owner.account.id, h)
    verifier, challenge = _pkce()

    async def exchange(code: str, **extra) -> tuple[int, dict]:
        r = await client.post(
            "/oauth/token",
            data={"grant_type": "authorization_code", "code": code, "code_verifier": verifier} | extra,
            auth=(app_json["client_id"], app_json["client_secret"]),
        )
        return r.status_code, r.json()

    code = await _code(client, h, app_json, owner.account.id, challenge)
    status, body = await exchange(code, code_verifier="wrong" * 10)
    assert (status, body["error"]) == (400, "invalid_grant")
    status, body = await exchange(code, redirect_uri="https://example.com/other")
    assert (status, body["error"]) == (400, "invalid_grant")
    status, tokens = await exchange(code)
    assert status == 200
    status, body = await exchange(code)  # used twice: it leaked
    assert (status, body["error"]) == (400, "invalid_grant")
    assert await _resolves(db_session, tokens["access_token"]) is None

    late = await _code(client, h, app_json, owner.account.id, challenge)
    await db_session.exec(  # type: ignore[call-overload]
        update(OAuthAuthorizationCode).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    status, body = await exchange(late)
    assert (status, body["error"]) == (400, "invalid_grant")


async def test_public_apps_use_pkce_without_a_secret(client, db_session):
    owner, h = await _seed(db_session, "-pub")
    app_json = await _create_app(client, owner.account.id, h, confidential=False)

    no_pkce = (
        await client.get("/api/v1/oauth/authorize", headers=h, params=_authorize_params(app_json, None))
    ).json()
    query = parse_qs(urlsplit(no_pkce["redirect_to"]).query)
    assert (query["error"], query["state"]) == (["invalid_request"], ["xyz"])

    verifier, challenge = _pkce()
    code = await _code(client, h, app_json, owner.account.id, challenge)
    with_secret = await client.post(
        "/oauth/token",
        data={"grant_type": "authorization_code", "code": code, "code_verifier": verifier},
        auth=(app_json["client_id"], "alo_secret_invented"),
    )
    assert (with_secret.status_code, with_secret.json()["error"]) == (401, "invalid_client")
    r = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "client_id": app_json["client_id"],
        },
    )
    assert r.status_code == 200, r.text
    assert (await _resolves(db_session, r.json()["access_token"])).user.id == owner.user.id


async def test_the_consent_checks_the_request_and_the_role(client, db_session):
    owner, h = await _seed(db_session, "-cons")
    agent, agent_h = await _seed_agent(db_session, owner.account.id, "-cons")
    app_json = await _create_app(client, owner.account.id, h)
    _, challenge = _pkce()
    url = "/api/v1/oauth/authorize"
    params = _authorize_params(app_json, challenge)

    assert (await client.get(url, params=params)).status_code == 401
    r = await client.get(url, headers=h, params=params | {"client_id": "alo_app_nope"})
    assert r.status_code == 400 and r.json()["message"]
    r = await client.get(url, headers=h, params=params | {"redirect_uri": "https://evil.example/cb"})
    assert r.status_code == 400 and r.json()["message"]
    for change, error in (({"response_type": "token"}, "unsupported_response_type"), ({"scope": "admin"}, "invalid_scope")):
        body = (await client.get(url, headers=h, params=params | change)).json()
        query = parse_qs(urlsplit(body["redirect_to"]).query)
        assert (query["error"], query["state"]) == ([error], ["xyz"])

    # An agent cannot let an app write in that account (but can let it read).
    preview = (await client.get(url, headers=agent_h, params=params)).json()
    shared = next(a for a in preview["accounts"] if a["id"] == owner.account.id)
    assert (shared["role"], shared["can_grant"]) == ("agent", False)
    r = await client.post(url, headers=agent_h, json=params | {"account_id": owner.account.id, "approve": True})
    assert r.status_code == 403 and r.json()["message"]
    code = await _code(client, agent_h, app_json, owner.account.id, challenge, scope="read")
    assert code.startswith("alo_code_")
    r = await client.post(url, headers=h, json=params | {"account_id": 999999, "approve": True})
    assert r.status_code == 403

    denied = (await client.post(url, headers=h, json=params | {"approve": False})).json()
    query = parse_qs(urlsplit(denied["redirect_to"]).query)
    assert (query["error"], query["state"]) == (["access_denied"], ["xyz"])
    assert agent.user.id


async def test_the_scope_follows_the_users_role_and_membership(client, db_session):
    owner, h = await _seed(db_session, "-role")
    app_json = await _create_app(client, owner.account.id, h)
    verifier, challenge = _pkce()
    code = await _code(client, h, app_json, owner.account.id, challenge)
    tokens = await _token(
        client, app_json, grant_type="authorization_code", code=code, code_verifier=verifier
    )

    membership = (
        await db_session.exec(
            select(AccountUser).where(
                AccountUser.account_id == owner.account.id, AccountUser.user_id == owner.user.id
            )
        )
    ).one()
    membership.role = ACCOUNT_USER_ROLE_AGENT
    db_session.add(membership)
    await db_session.flush()
    assert (await _resolves(db_session, tokens["access_token"])).scope == "read"

    await db_session.delete(membership)
    await db_session.flush()
    assert await _resolves(db_session, tokens["access_token"]) is None


async def test_token_endpoint_errors_and_revocation(client, db_session):
    owner, h = await _seed(db_session, "-err")
    app_json = await _create_app(client, owner.account.id, h)

    r = await client.post(
        "/oauth/token",
        data={"grant_type": "authorization_code", "code": "x"},
        auth=(app_json["client_id"], "alo_secret_wrong"),
    )
    assert (r.status_code, r.json()["error"]) == (401, "invalid_client")
    assert r.headers["www-authenticate"].startswith("Basic")
    r = await client.post(
        "/oauth/token",
        data={"grant_type": "password"},
        auth=(app_json["client_id"], app_json["client_secret"]),
    )
    assert (r.status_code, r.json()["error"]) == (400, "unsupported_grant_type")

    verifier, challenge = _pkce()
    code = await _code(client, h, app_json, owner.account.id, challenge)
    tokens = await _token(
        client, app_json, grant_type="authorization_code", code=code, code_verifier=verifier
    )
    r = await client.post(
        "/oauth/revoke",
        data={"token": tokens["access_token"]},
        auth=(app_json["client_id"], app_json["client_secret"]),
    )
    assert r.status_code == 200
    assert await _resolves(db_session, tokens["access_token"]) is None
    r = await client.post(
        "/oauth/revoke",
        data={"token": "alo_at_unknown"},
        auth=(app_json["client_id"], app_json["client_secret"]),
    )
    assert r.status_code == 200  # RFC 7009: unknown tokens are not an error


async def test_discovery_and_the_mcp_gate(client):
    base_url = get_settings().app_base_url.rstrip("/")
    metadata = (await client.get("/.well-known/oauth-authorization-server")).json()
    assert (metadata["issuer"], metadata["token_endpoint"], metadata["code_challenge_methods_supported"]) == (
        base_url,
        f"{base_url}/oauth/token",
        ["S256"],
    )
    resource = (await client.get("/.well-known/oauth-protected-resource/mcp")).json()
    assert resource == (await client.get("/.well-known/oauth-protected-resource")).json()
    assert (resource["resource"], resource["authorization_servers"]) == (f"{base_url}/mcp", [base_url])

    for headers in ({}, {"Authorization": "Bearer alo_at_invented"}):
        r = await client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert r.status_code == 401
        assert r.headers["www-authenticate"] == (
            f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource/mcp"'
        )
    # Other paths are untouched by the gate.
    assert (await client.get("/no-such-route")).json() == {"detail": "Not Found"}
