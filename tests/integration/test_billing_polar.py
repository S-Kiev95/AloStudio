"""F2 paso 3 — Polar: webhook signatures (standard and legacy secrets),
subscription events applied once per webhook-id, never raising, and the
checkout / plans calls (Polar mocked with respx)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.billing.models import AccountSubscription, BillingEvent
from app.domains.billing.polar import verify_signature
from app.main import app

pytestmark = pytest.mark.integration

KEY = b"0123456789abcdef0123456789abcdef"
SECRET = "whsec_" + base64.b64encode(KEY).decode()
SANDBOX = "https://sandbox-api.polar.sh/v1"


def _sign(body: bytes, webhook_id: str, ts: int, key: bytes = KEY) -> str:
    mac = hmac.new(key, f"{webhook_id}.{ts}.".encode() + body, hashlib.sha256).digest()
    return "v1," + base64.b64encode(mac).decode()


def test_signatures_standard_legacy_and_replays():
    body = b'{"type":"x"}'
    now = int(time.time())
    assert verify_signature(
        body=body, webhook_id="w1", timestamp=str(now), signature=_sign(body, "w1", now), secret=SECRET
    )
    legacy = "whsec_not-base64!!"
    assert verify_signature(
        body=body,
        webhook_id="w1",
        timestamp=str(now),
        signature=_sign(body, "w1", now, key=legacy.encode()),
        secret=legacy,
    )
    assert not verify_signature(
        body=b'{"type":"y"}', webhook_id="w1", timestamp=str(now), signature=_sign(body, "w1", now), secret=SECRET
    )
    old = now - 3600
    assert not verify_signature(
        body=body, webhook_id="w1", timestamp=str(old), signature=_sign(body, "w1", old), secret=SECRET
    )
    assert not verify_signature(body=body, webhook_id="w1", timestamp=str(now), signature="", secret=SECRET)


@pytest.fixture
async def client(db_session, monkeypatch) -> AsyncIterator[AsyncClient]:
    settings = get_settings()
    monkeypatch.setattr(settings, "polar_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "polar_access_token", "polar_oat_test")
    monkeypatch.setattr(settings, "polar_server", "sandbox")

    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _owner(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@billing.example.com",
            account_name=f"BILL{suffix}",
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


async def _post(client, payload: dict, webhook_id: str, *, secret_ok: bool = True):
    body = json.dumps(payload).encode()
    now = int(time.time())
    sig = _sign(body, webhook_id, now) if secret_ok else "v1,AAAA"
    return await client.post(
        "/webhooks/polar",
        content=body,
        headers={
            "webhook-id": webhook_id,
            "webhook-timestamp": str(now),
            "webhook-signature": sig,
            "content-type": "application/json",
        },
    )


async def test_subscription_webhooks_update_the_account_once(client, db_session):
    owner, headers = await _owner(db_session, "-hook")
    account_id = owner.account.id
    event = {
        "type": "subscription.active",
        "data": {
            "id": "sub_1",
            "status": "active",
            "product_id": "prod_pro",
            "product": {"id": "prod_pro", "name": "Pro"},
            "customer": {"id": "cus_1", "external_id": str(account_id)},
            "metadata": {"account_id": str(account_id)},
            "current_period_end": "2026-12-15T00:00:00Z",
            "cancel_at_period_end": False,
        },
    }
    assert (await _post(client, event, "wh_1")).status_code == 202
    assert (await _post(client, event, "wh_1")).status_code == 202  # Polar retry
    status = (await client.get(f"/api/v1/accounts/{account_id}/billing", headers=headers)).json()
    assert status["status"] == "active"
    assert status["has_access"] is True
    assert status["plan_name"] == "Pro"
    rows = (await db_session.exec(select(BillingEvent).where(BillingEvent.webhook_id == "wh_1"))).all()
    assert len(rows) == 1

    canceled = {**event, "type": "subscription.revoked", "data": {**event["data"], "status": "canceled"}}
    await _post(client, canceled, "wh_2")
    sub = (
        await db_session.exec(select(AccountSubscription).where(AccountSubscription.account_id == account_id))
    ).one()
    assert sub.status == "canceled"


async def test_bad_signature_and_unknown_account(client, db_session):
    assert (await _post(client, {"type": "subscription.active", "data": {}}, "wh_bad", secret_ok=False)).status_code == 403
    resp = await _post(client, {"type": "subscription.active", "data": {"id": "sub_x", "status": "active"}}, "wh_orphan")
    assert resp.status_code == 202  # stored with its error, never a 500
    event = (await db_session.exec(select(BillingEvent).where(BillingEvent.webhook_id == "wh_orphan"))).one()
    assert event.processed_at is None
    assert "without account" in (event.error or "")


async def test_plans_and_checkout(client, db_session):
    owner, headers = await _owner(db_session, "-checkout")
    base = f"/api/v1/accounts/{owner.account.id}/billing"
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{SANDBOX}/products/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "prod_pro", "name": "Pro", "recurring_interval": "month",
                         "prices": [{"price_amount": 4900, "price_currency": "usd"}]},
                        {"id": "prod_basic", "name": "Básico", "recurring_interval": "month",
                         "prices": [{"price_amount": 1900, "price_currency": "usd"}]},
                    ]
                },
            )
        )
        checkout = mock.post(f"{SANDBOX}/checkouts/").mock(
            return_value=httpx.Response(201, json={"url": "https://sandbox.polar.sh/checkout/abc"})
        )
        plans = (await client.get(f"{base}/plans", headers=headers)).json()["plans"]
        assert [p["name"] for p in plans] == ["Básico", "Pro"]
        assert plans[0]["amount"] == 19 and plans[0]["currency"] == "USD"
        resp = await client.post(f"{base}/checkout", json={"product_id": "prod_pro"}, headers=headers)
    assert resp.json() == {"url": "https://sandbox.polar.sh/checkout/abc"}
    sent = json.loads(checkout.calls.last.request.content)
    assert sent["products"] == ["prod_pro"]
    assert sent["external_customer_id"] == str(owner.account.id)
    assert sent["metadata"] == {"account_id": str(owner.account.id)}
    assert checkout.calls.last.request.headers["Authorization"] == "Bearer polar_oat_test"
