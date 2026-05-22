"""Integration tests for Instagram connection (I.10 — manual mode).

Covers connection-capability tracking (``login_type``), the manual
connect path, and the delete-media capability gate (Instagram Login
can't delete via Meta's API).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.instagram import oauth as ig_oauth
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import connect_service as csvc
from app.domains.instagram import publishing_service as ig_svc
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = "https://graph.facebook.com/v23.0"


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


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igc2.example.com",
            account_name=f"IGC2{suffix}",
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


async def _ig_channel(db_session, owner, suffix):
    res = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": f"ig-conn-{suffix}",
                "access_token": "PAGE-TOKEN",
            },
        ),
    ).perform()
    return res.inbox, res.channel


async def _published_post(db_session, owner, inbox, channel, ig_media_id):
    post = await ig_svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/p.jpg"},
    )
    post.state = "published"
    post.ig_media_id = ig_media_id
    db_session.add(post)
    await db_session.flush()
    return post


# ---------------------------------------------------------------------------
# Capability tracking
# ---------------------------------------------------------------------------
async def test_record_connection_and_capability(db_session):
    owner, _ = await _seed(db_session, "-cap")
    _, channel = await _ig_channel(db_session, owner, "-cap")

    # No setting yet → default allowed (legacy channels).
    assert (
        await csvc.can_delete_media(
            db_session, channel_instagram_id=channel.id
        )
        is True
    )

    await csvc.record_connection(
        db_session,
        channel_instagram_id=channel.id,
        login_type="instagram",
    )
    assert (
        await csvc.can_delete_media(
            db_session, channel_instagram_id=channel.id
        )
        is False
    )

    # Upsert to facebook → allowed again.
    await csvc.record_connection(
        db_session,
        channel_instagram_id=channel.id,
        login_type="facebook",
    )
    assert (
        await csvc.can_delete_media(
            db_session, channel_instagram_id=channel.id
        )
        is True
    )


async def test_record_connection_invalid_login_type(db_session):
    owner, _ = await _seed(db_session, "-inv")
    _, channel = await _ig_channel(db_session, owner, "-inv")
    with pytest.raises(ChatwootHTTPException) as exc:
        await csvc.record_connection(
            db_session,
            channel_instagram_id=channel.id,
            login_type="bogus",
        )
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# Manual connect
# ---------------------------------------------------------------------------
async def test_connect_manual_creates_inbox_channel_settings(db_session):
    owner, _ = await _seed(db_session, "-man")
    result = await csvc.connect_manual(
        db_session,
        account=owner.account,
        name="My IG",
        instagram_id="17841400000099999",
        access_token="PERMA-TOKEN",
        login_type="facebook",
    )
    assert result["inbox_id"] is not None
    assert result["channel_instagram_id"] is not None
    assert result["login_type"] == "facebook"
    setting = await csvc.get_channel_setting(
        db_session, channel_instagram_id=result["channel_instagram_id"]
    )
    assert setting is not None
    assert setting.connect_method == "manual"


# ---------------------------------------------------------------------------
# Delete-media capability gate
# ---------------------------------------------------------------------------
@respx.mock
async def test_delete_blocked_on_instagram_login(db_session):
    owner, _ = await _seed(db_session, "-delblk")
    inbox, channel = await _ig_channel(db_session, owner, "-delblk")
    await csvc.record_connection(
        db_session, channel_instagram_id=channel.id, login_type="instagram"
    )
    post = await _published_post(db_session, owner, inbox, channel, "IGM1")
    # No respx route registered — the gate must reject BEFORE any Meta call.
    with pytest.raises(ChatwootHTTPException) as exc:
        await ig_svc.delete_media_on_meta(
            db_session, account_id=owner.account.id, post_id=post.id
        )
    assert exc.value.status_code == 422
    assert "Instagram Login" in exc.value.detail["message"]


@respx.mock
async def test_delete_allowed_on_facebook_login(db_session):
    owner, _ = await _seed(db_session, "-delok")
    inbox, channel = await _ig_channel(db_session, owner, "-delok")
    await csvc.record_connection(
        db_session, channel_instagram_id=channel.id, login_type="facebook"
    )
    post = await _published_post(db_session, owner, inbox, channel, "IGM2")
    respx.delete(f"{GRAPH}/IGM2").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    result = await ig_svc.delete_media_on_meta(
        db_session, account_id=owner.account.id, post_id=post.id
    )
    assert result.state == "deleted"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
async def test_connect_manual_requires_auth(client):
    resp = await client.post(
        "/api/v1/accounts/1/instagram_channels/connect_manual",
        json={
            "name": "x",
            "instagram_id": "1",
            "access_token": "t",
        },
    )
    assert resp.status_code == 401


async def test_connect_manual_endpoint(client, db_session):
    owner, headers = await _seed(db_session, "-ep")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_channels/connect_manual",
        json={
            "name": "My IG",
            "instagram_id": "17841400000088888",
            "access_token": "PERMA",
            "login_type": "instagram",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["login_type"] == "instagram"

    settings = await client.get(
        f"/api/v1/accounts/{owner.account.id}/instagram_channels/"
        f"{body['channel_instagram_id']}/settings",
        headers=headers,
    )
    assert settings.status_code == 200
    assert settings.json()["can_delete_media"] is False


async def test_connect_manual_invalid_login_type(client, db_session):
    owner, headers = await _seed(db_session, "-epinv")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_channels/connect_manual",
        json={
            "name": "x",
            "instagram_id": "1",
            "access_token": "t",
            "login_type": "bogus",
        },
        headers=headers,
    )
    # Rejected by the schema Literal (422).
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# OAuth — Facebook Login (I.10b)
# ---------------------------------------------------------------------------
@pytest.fixture
def meta_oauth_config():
    settings = get_settings()
    orig = (
        settings.meta_app_id,
        settings.meta_app_secret,
        settings.meta_oauth_redirect_uri,
    )
    settings.meta_app_id = "APPID"
    settings.meta_app_secret = "APPSECRET"
    settings.meta_oauth_redirect_uri = (
        "https://app.example.com/api/v1/instagram/oauth/callback"
    )
    try:
        yield settings
    finally:
        (
            settings.meta_app_id,
            settings.meta_app_secret,
            settings.meta_oauth_redirect_uri,
        ) = orig


def test_oauth_state_sign_verify_roundtrip():
    state = csvc.sign_oauth_state(42, flow="facebook")
    payload = csvc.verify_oauth_state(state)
    assert payload["account_id"] == 42
    assert payload["flow"] == "facebook"


def test_oauth_state_tampered_rejected():
    state = csvc.sign_oauth_state(42, flow="facebook")
    tampered = state[:-1] + ("0" if state[-1] != "0" else "1")
    with pytest.raises(ChatwootHTTPException) as exc:
        csvc.verify_oauth_state(tampered)
    assert exc.value.status_code == 401


def test_build_facebook_login_url(meta_oauth_config):
    url = ig_oauth.build_facebook_login_url(
        redirect_uri="https://app.example.com/cb", state="ST8"
    )
    assert "client_id=APPID" in url
    assert "state=ST8" in url
    assert "instagram_content_publish" in url
    assert "dialog/oauth" in url


@respx.mock
async def test_complete_facebook_oauth_happy_path(db_session, meta_oauth_config):
    owner, _ = await _seed(db_session, "-fbok")
    # token exchange (short then long) hit the same URL.
    respx.get(f"{GRAPH}/oauth/access_token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "SHORT"}),
            httpx.Response(
                200, json={"access_token": "LONG", "expires_in": 5183944}
            ),
        ]
    )
    respx.get(f"{GRAPH}/me/accounts").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "PAGE1",
                        "name": "Mi Negocio",
                        "access_token": "PAGE_TOKEN_PERMA",
                        "instagram_business_account": {"id": "17841999"},
                    }
                ]
            },
        )
    )
    state = csvc.sign_oauth_state(owner.account.id, flow="facebook")
    result = await csvc.complete_facebook_oauth(
        db_session, code="CODE", state=state
    )
    assert result["login_type"] == "facebook"
    assert result["instagram_id"] == "17841999"
    assert result["page_id"] == "PAGE1"
    setting = await csvc.get_channel_setting(
        db_session, channel_instagram_id=result["channel_instagram_id"]
    )
    assert setting.connect_method == "oauth"
    assert setting.login_type == "facebook"


@respx.mock
async def test_complete_facebook_oauth_no_ig_page_422(db_session, meta_oauth_config):
    owner, _ = await _seed(db_session, "-fbnoig")
    respx.get(f"{GRAPH}/oauth/access_token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "S"}),
            httpx.Response(200, json={"access_token": "L"}),
        ]
    )
    respx.get(f"{GRAPH}/me/accounts").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "P", "name": "No IG", "access_token": "t"}]},
        )
    )
    state = csvc.sign_oauth_state(owner.account.id, flow="facebook")
    with pytest.raises(ChatwootHTTPException) as exc:
        await csvc.complete_facebook_oauth(
            db_session, code="CODE", state=state
        )
    assert exc.value.status_code == 422


async def test_complete_facebook_oauth_bad_state(db_session, meta_oauth_config):
    with pytest.raises(ChatwootHTTPException) as exc:
        await csvc.complete_facebook_oauth(
            db_session, code="CODE", state="garbage.sig"
        )
    assert exc.value.status_code == 401


async def test_connect_start_endpoint(client, db_session, meta_oauth_config):
    owner, headers = await _seed(db_session, "-start")
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/instagram_channels/connect/start",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "dialog/oauth" in resp.json()["authorize_url"]
    assert "client_id=APPID" in resp.json()["authorize_url"]


async def test_connect_start_unconfigured_422(client, db_session):
    owner, headers = await _seed(db_session, "-startno")
    # No meta_oauth_config fixture → app_id/redirect_uri empty.
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/instagram_channels/connect/start",
        headers=headers,
    )
    assert resp.status_code == 422


@respx.mock
async def test_oauth_callback_endpoint(client, db_session, meta_oauth_config):
    owner, _ = await _seed(db_session, "-cb")
    respx.get(f"{GRAPH}/oauth/access_token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "S"}),
            httpx.Response(200, json={"access_token": "L"}),
        ]
    )
    respx.get(f"{GRAPH}/me/accounts").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "PG",
                        "name": "Biz",
                        "access_token": "PT",
                        "instagram_business_account": {"id": "178412345"},
                    }
                ]
            },
        )
    )
    state = csvc.sign_oauth_state(owner.account.id, flow="facebook")
    resp = await client.get(
        "/api/v1/instagram/oauth/callback",
        params={"code": "CODE", "state": state},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["instagram_id"] == "178412345"


async def test_oauth_callback_missing_code_400(client):
    resp = await client.get(
        "/api/v1/instagram/oauth/callback", params={"state": "x"}
    )
    assert resp.status_code == 400
