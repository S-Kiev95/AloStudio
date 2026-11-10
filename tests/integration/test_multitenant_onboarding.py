"""F2 step 2 — client onboarding on a multitenant install.

* ``/webhooks/whatsapp``: one app-level webhook, each change routed to the
  account that connected the number it names.
* WhatsApp Embedded Signup: the number comes from Meta (code exchange +
  ``debug_token``), never from a form; a failed connection saves nothing.
* ``MULTITENANT``: Meta channels can't be typed in by hand, signup confirms
  the email, and the installation settings need a super admin.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import clear_settings_overlay, get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations.models import Message
from app.domains.inboxes.models import (
    WHATSAPP_PROVIDER_CLOUD,
    Inbox,
    WhatsappChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import User
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = "https://graph.facebook.com/v23.0"


@pytest.fixture(autouse=True)
def multitenant(monkeypatch):
    """A multitenant install with Embedded Signup configured. Set through
    the environment: the settings overlay comes from the database."""
    for name, value in {
        "MULTITENANT": "true",
        "META_APP_ID": "111",
        "META_APP_SECRET": "app-secret",
        "WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID": "cfg-1",
        "WHATSAPP_VERIFY_TOKEN": "vt-1",
        "APP_BASE_URL": "https://app.example.com",
        "META_GRAPH_API_VERSION": "v23.0",
        "META_VERIFY_WEBHOOK_SIGNATURE": "false",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("WHATSAPP_CLOUD_BASE_URL", raising=False)
    clear_settings_overlay()
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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


async def _account(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@onboard.example.com",
            account_name=f"Onboard{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _whatsapp_inbox(db_session, owner, *, phone: str, number_id: str) -> Inbox:
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"WA {phone}",
            channel_type="whatsapp",
            channel_params={
                "phone_number": phone,
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "tok",
                    "phone_number_id": number_id,
                    "business_account_id": "waba-x",
                },
            },
        ),
    ).perform()
    return result.inbox


def _change(number_id: str, wamid: str, customer: str, text: str) -> dict[str, Any]:
    return {
        "field": "messages",
        "value": {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": number_id},
            "contacts": [{"profile": {"name": "Cliente"}, "wa_id": customer}],
            "messages": [
                {
                    "from": customer,
                    "id": wamid,
                    "timestamp": "1700000000",
                    "type": "text",
                    "text": {"body": text},
                }
            ],
        },
    }


async def _texts(db_session, inbox: Inbox) -> list[str]:
    rows = (await db_session.exec(select(Message).where(Message.inbox_id == inbox.id))).all()
    return sorted(m.content for m in rows if m.content)


# ---------------------------------------------------------------------------
# App-level WhatsApp webhook
# ---------------------------------------------------------------------------
async def test_app_webhook_handshake_uses_the_installation_token(client):
    ok = await client.get(
        "/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.challenge": "42", "hub.verify_token": "vt-1"},
    )
    assert ok.status_code == 200
    assert ok.text == "42"
    wrong = await client.get(
        "/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.challenge": "42", "hub.verify_token": "nope"},
    )
    assert wrong.status_code == 401


async def test_app_webhook_routes_each_change_to_its_account(client, db_session):
    a, _ = await _account(db_session, "-route-a")
    b, _ = await _account(db_session, "-route-b")
    inbox_a = await _whatsapp_inbox(db_session, a, phone="+59891000001", number_id="pn-a")
    inbox_b = await _whatsapp_inbox(db_session, b, phone="+59891000002", number_id="pn-b")
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-x",
                "changes": [
                    _change("pn-a", "wamid.a1", "59899000001", "Hola A"),
                    _change("pn-b", "wamid.b1", "59899000002", "Hola B"),
                    _change("pn-unknown", "wamid.u1", "59899000003", "Nadie"),
                ],
            }
        ],
    }
    resp = await client.post("/webhooks/whatsapp", content=json.dumps(payload))
    assert resp.status_code == 200

    assert await _texts(db_session, inbox_a) == ["Hola A"]
    assert await _texts(db_session, inbox_b) == ["Hola B"]


# ---------------------------------------------------------------------------
# Embedded Signup
# ---------------------------------------------------------------------------
def _meta(
    mock: respx.MockRouter,
    *,
    granted_waba: str = "waba-1",
    verification: str = "VERIFIED",
    subscribe_status: int = 200,
) -> dict[str, respx.Route]:
    routes = {
        "exchange": mock.get(f"{GRAPH}/oauth/access_token").mock(
            return_value=httpx.Response(200, json={"access_token": "biz-token"})
        ),
        "debug": mock.get(f"{GRAPH}/debug_token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "is_valid": True,
                        "app_id": "111",
                        "granular_scopes": [
                            {
                                "scope": "whatsapp_business_management",
                                "target_ids": [granted_waba],
                            }
                        ],
                    }
                },
            )
        ),
        "phones": mock.get(f"{GRAPH}/waba-1/phone_numbers").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "pn-1",
                            "display_phone_number": "+598 92 111 222",
                            "verified_name": "Tienda Uno",
                            "code_verification_status": verification,
                            "platform_type": "CLOUD_API",
                        }
                    ]
                },
            )
        ),
        "subscribe": mock.post(f"{GRAPH}/waba-1/subscribed_apps").mock(
            return_value=httpx.Response(subscribe_status, json={"success": subscribe_status == 200})
        ),
        "register": mock.post(f"{GRAPH}/pn-1/register").mock(
            return_value=httpx.Response(200, json={"success": True})
        ),
    }
    return routes


SIGNUP_BODY = {"code": "code-1", "waba_id": "waba-1", "phone_number_id": "pn-1"}


async def _channel_for(db_session, phone: str) -> WhatsappChannel | None:
    return (
        await db_session.exec(select(WhatsappChannel).where(WhatsappChannel.phone_number == phone))
    ).first()


async def test_embedded_signup_info_says_what_the_button_needs(client, db_session):
    a, headers = await _account(db_session, "-info")
    resp = await client.get(
        f"/api/v1/accounts/{a.account.id}/whatsapp/embedded_signup", headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["app_id"] == "111" and body["config_id"] == "cfg-1"


async def test_embedded_signup_connects_the_number_from_meta(client, db_session):
    a, headers = await _account(db_session, "-es-ok")
    with respx.mock(assert_all_called=False) as mock:
        routes = _meta(mock)
        resp = await client.post(
            f"/api/v1/accounts/{a.account.id}/whatsapp/embedded_signup",
            headers=headers,
            json=SIGNUP_BODY,
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] is True

    channel = await _channel_for(db_session, "+59892111222")
    assert channel is not None and channel.account_id == a.account.id
    config = channel.provider_config
    assert config["api_key"] == "biz-token"
    assert config["phone_number_id"] == "pn-1"
    assert config["business_account_id"] == "waba-1"

    # Subscribed, then pointed at the app-level webhook.
    calls = routes["subscribe"].calls
    assert len(calls) == 2
    override = json.loads(calls[1].request.content)
    assert override["override_callback_uri"] == "https://app.example.com/webhooks/whatsapp"
    assert override["verify_token"] == "vt-1"
    # Already verified: no registration.
    assert not routes["register"].called


async def test_embedded_signup_registers_a_number_that_needs_it(client, db_session):
    a, headers = await _account(db_session, "-es-reg")
    with respx.mock(assert_all_called=False) as mock:
        routes = _meta(mock, verification="NOT_VERIFIED")
        resp = await client.post(
            f"/api/v1/accounts/{a.account.id}/whatsapp/embedded_signup",
            headers=headers,
            json=SIGNUP_BODY,
        )
    assert resp.status_code == 200, resp.text
    sent = json.loads(routes["register"].calls.last.request.content)
    assert sent["messaging_product"] == "whatsapp"
    assert len(sent["pin"]) == 6 and sent["pin"].isdigit()
    channel = await _channel_for(db_session, "+59892111222")
    assert channel is not None
    assert channel.provider_config["verification_pin"] == sent["pin"]


async def test_embedded_signup_refuses_a_token_without_that_waba(client, db_session):
    a, headers = await _account(db_session, "-es-scope")
    with respx.mock(assert_all_called=False) as mock:
        routes = _meta(mock, granted_waba="someone-elses-waba")
        resp = await client.post(
            f"/api/v1/accounts/{a.account.id}/whatsapp/embedded_signup",
            headers=headers,
            json=SIGNUP_BODY,
        )
    assert resp.status_code == 422
    assert not routes["subscribe"].called
    assert await _channel_for(db_session, "+59892111222") is None


async def test_embedded_signup_refuses_a_number_of_another_account(client, db_session):
    a, headers = await _account(db_session, "-es-mine")
    b, _ = await _account(db_session, "-es-theirs")
    await _whatsapp_inbox(db_session, b, phone="+59892111222", number_id="pn-1")
    with respx.mock(assert_all_called=False) as mock:
        routes = _meta(mock)
        resp = await client.post(
            f"/api/v1/accounts/{a.account.id}/whatsapp/embedded_signup",
            headers=headers,
            json=SIGNUP_BODY,
        )
    assert resp.status_code == 422
    assert "otra cuenta" in resp.json()["message"]
    assert not routes["subscribe"].called


async def test_embedded_signup_saves_nothing_when_the_subscription_fails(client, db_session):
    a, headers = await _account(db_session, "-es-fail")
    with respx.mock(assert_all_called=False) as mock:
        _meta(mock, subscribe_status=400)
        resp = await client.post(
            f"/api/v1/accounts/{a.account.id}/whatsapp/embedded_signup",
            headers=headers,
            json=SIGNUP_BODY,
        )
    assert resp.status_code == 422
    assert await _channel_for(db_session, "+59892111222") is None


# ---------------------------------------------------------------------------
# MULTITENANT switches
# ---------------------------------------------------------------------------
async def test_meta_channels_can_not_be_typed_in_by_hand(client, db_session):
    a, headers = await _account(db_session, "-manual")
    url = f"/api/v1/accounts/{a.account.id}/inboxes"
    for channel in (
        {"type": "whatsapp", "phone_number": "+59893000000", "provider": "whatsapp_cloud"},
        {"type": "instagram", "instagram_id": "17841400000000000", "access_token": "t"},
        {"type": "facebook", "page_id": "1000", "page_access_token": "t"},
    ):
        resp = await client.post(url, headers=headers, json={"name": "Manual", "channel": channel})
        assert resp.status_code == 422, channel["type"]
        assert "botón de Meta" in resp.json()["message"]

    # Channels that are not Meta's still work.
    resp = await client.post(url, headers=headers, json={"name": "API", "channel": {"type": "api"}})
    assert resp.status_code == 200, resp.text


async def test_signup_confirms_the_email_before_signing_in(client, db_session, monkeypatch):
    monkeypatch.setenv("ENABLE_ACCOUNT_SIGNUP", "true")
    get_settings.cache_clear()
    sent: list[str] = []

    async def _capture(user, raw_token):
        sent.append(user.email)

    monkeypatch.setattr("app.domains.auth.confirmation._dispatch_confirmation_email", _capture)
    resp = await client.post(
        "/api/v1/accounts",
        json={
            "account_name": "Tienda Nueva",
            "user_full_name": "Dueña",
            "email": "duena@tienda-nueva.example.com",
            "password": "Password123!",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"email": "duena@tienda-nueva.example.com"}
    # No session until the link is followed.
    assert "access-token" not in {k.lower() for k in resp.headers}
    assert sent == ["duena@tienda-nueva.example.com"]
    user = (
        await db_session.exec(select(User).where(User.email == "duena@tienda-nueva.example.com"))
    ).first()
    assert user is not None and user.confirmed_at is None


async def test_installation_settings_need_a_super_admin(client, db_session):
    from app.domains.installation.deps import has_any_super_admin

    _owner, headers = await _account(db_session, "-operator")
    assert await has_any_super_admin(db_session) is False
    resp = await client.get("/api/v1/installation/configs", headers=headers)
    # On a dedicated install the first account's admin gets in while no
    # super admin exists; on a multitenant one that would be a client.
    assert resp.status_code == 401


async def test_public_settings_tell_the_login_page_what_to_show(client, monkeypatch):
    monkeypatch.setenv("ENABLE_ACCOUNT_SIGNUP", "true")
    get_settings.cache_clear()
    resp = await client.get("/api/v1/installation/public")
    assert resp.status_code == 200
    assert resp.json() == {"signup_enabled": True, "multitenant": True}
