"""F2 paso 3 — Polar: webhook signatures (standard and legacy secrets),
subscription events applied once per webhook-id, never raising, and the
checkout / plans calls (Polar mocked with respx), and the 402 gate for
accounts without a plan on a multitenant install."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from decimal import Decimal

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import clear_settings_overlay, get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.billing.models import AccountSubscription, BillingEvent
from app.domains.billing.polar import verify_signature
from app.main import app
from app.mcp.service import MCPAuthError, create_token, resolve_token

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
                         "trial_interval": "day", "trial_interval_count": 30,
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
        assert [p["trial_days"] for p in plans] == [30, None]
        resp = await client.post(f"{base}/checkout", json={"product_id": "prod_pro"}, headers=headers)
    assert resp.json() == {"url": "https://sandbox.polar.sh/checkout/abc"}
    sent = json.loads(checkout.calls.last.request.content)
    assert sent["products"] == ["prod_pro"]
    assert sent["external_customer_id"] == str(owner.account.id)
    assert sent["metadata"] == {"account_id": str(owner.account.id)}
    assert checkout.calls.last.request.headers["Authorization"] == "Bearer polar_oat_test"


@pytest.fixture
def multitenant(monkeypatch):
    monkeypatch.setenv("MULTITENANT", "true")
    clear_settings_overlay()
    get_settings.cache_clear()
    yield
    clear_settings_overlay()
    get_settings.cache_clear()


async def _set_status(db_session, account_id: int, status: str) -> None:
    sub = (
        await db_session.exec(select(AccountSubscription).where(AccountSubscription.account_id == account_id))
    ).first() or AccountSubscription(account_id=account_id)
    sub.status = status
    db_session.add(sub)
    await db_session.flush()


async def test_multitenant_without_a_plan_gets_402_but_can_pay(multitenant, client, db_session):
    owner, headers = await _owner(db_session, "-gate")
    base = f"/api/v1/accounts/{owner.account.id}"
    resp = await client.get(f"{base}/conversations", headers=headers)
    assert resp.status_code == 402
    assert resp.json()["code"] == "subscription_required"
    assert (await client.post(f"{base}/labels", json={"title": "x"}, headers=headers)).status_code == 402
    # The account itself and billing stay open, to choose a plan and pay.
    assert (await client.get(base, headers=headers)).status_code == 200
    assert (await client.get(f"{base}/billing", headers=headers)).json()["has_access"] is False

    for status, code in (("trialing", 200), ("active", 200), ("past_due", 402), ("canceled", 402)):
        await _set_status(db_session, owner.account.id, status)
        assert (await client.get(f"{base}/conversations", headers=headers)).status_code == code, status


async def test_single_tenant_never_asks_for_a_plan(client, db_session):
    owner, headers = await _owner(db_session, "-single")
    resp = await client.get(f"/api/v1/accounts/{owner.account.id}/conversations", headers=headers)
    assert resp.status_code == 200


async def test_mcp_token_needs_a_plan_on_multitenant(multitenant, client, db_session):
    owner, _ = await _owner(db_session, "-mcp")
    token = await create_token(db_session, account_id=owner.account.id, name="bot")
    with pytest.raises(MCPAuthError):
        await resolve_token(db_session, token_value=token.token)
    await _set_status(db_session, owner.account.id, "active")
    ctx = await resolve_token(db_session, token_value=token.token)
    assert ctx.account.id == owner.account.id


async def test_checkout_retries_without_an_email_polar_refuses(client, db_session):
    owner, headers = await _owner(db_session, "-mail")
    refused = {"detail": [
        {"type": "value_error", "loc": ["body", "CheckoutProductsCreate", "customer_email"],
         "msg": "The domain name example.com does not accept email."},
        {"type": "missing", "loc": ["body", "CheckoutProductCreate", "product_id"], "msg": "Field required"},
    ]}
    with respx.mock(assert_all_called=False) as mock:
        checkout = mock.post(f"{SANDBOX}/checkouts/").mock(
            side_effect=[
                httpx.Response(422, json=refused),
                httpx.Response(201, json={"url": "https://sandbox.polar.sh/checkout/xyz"}),
            ]
        )
        resp = await client.post(
            f"/api/v1/accounts/{owner.account.id}/billing/checkout",
            json={"product_id": "prod_pro"},
            headers=headers,
        )
    assert resp.json() == {"url": "https://sandbox.polar.sh/checkout/xyz"}
    assert json.loads(checkout.calls[0].request.content)["customer_email"]
    assert json.loads(checkout.calls[1].request.content)["customer_email"] is None


async def test_polar_validation_errors_read_plainly(client, db_session):
    owner, headers = await _owner(db_session, "-err")
    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{SANDBOX}/checkouts/").mock(
            return_value=httpx.Response(422, json={"detail": [
                {"type": "value_error", "loc": ["body", "X", "products"], "msg": "Product is archived."},
                {"type": "missing", "loc": ["body", "Y", "product_id"], "msg": "Field required"},
            ]})
        )
        resp = await client.post(
            f"/api/v1/accounts/{owner.account.id}/billing/checkout",
            json={"product_id": "prod_old"},
            headers=headers,
        )
    assert resp.status_code == 422
    assert resp.json()["message"] == "Product is archived."


BASIC = {"plan": "basic", "channels": "meta", "whatsapp_calls": False, "usage_cap_usd_cents": 500}
MAX = {"plan": "max", "channels": "all", "whatsapp_calls": True, "usage_cap_usd_cents": 4000}


async def _with_plan(db_session, account_id: int, features: dict) -> None:
    await _set_status(db_session, account_id, "active")
    sub = (
        await db_session.exec(select(AccountSubscription).where(AccountSubscription.account_id == account_id))
    ).one()
    sub.plan_features = features
    db_session.add(sub)
    await db_session.flush()


async def test_the_plan_comes_from_the_products_metadata(client, db_session):
    owner, _ = await _owner(db_session, "-meta")
    event = {
        "type": "subscription.active",
        "data": {
            "id": "sub_meta",
            "status": "active",
            "product": {"id": "prod_basic", "name": "Basic", "metadata": BASIC},
            "customer": {"id": "cus_meta", "external_id": str(owner.account.id)},
            "metadata": {"account_id": str(owner.account.id)},
        },
    }
    assert (await _post(client, event, "wh_meta")).status_code == 202
    sub = (
        await db_session.exec(select(AccountSubscription).where(AccountSubscription.account_id == owner.account.id))
    ).one()
    assert sub.plan_features == BASIC


async def test_basic_connects_only_metas_networks(multitenant, client, db_session):
    owner, headers = await _owner(db_session, "-basic")
    await _with_plan(db_session, owner.account.id, BASIC)
    base = f"/api/v1/accounts/{owner.account.id}"
    telegram = await client.post(
        f"{base}/inboxes",
        json={"name": "TG", "channel": {"type": "telegram", "bot_token": "1:x", "bot_name": "B"}},
        headers=headers,
    )
    assert telegram.status_code == 403
    assert telegram.json()["code"] == "plan_upgrade_required"
    # Own channels come with every plan.
    api = await client.post(
        f"{base}/inboxes",
        json={"name": "API", "channel": {"type": "api", "webhook_url": "https://example.com/hook"}},
        headers=headers,
    )
    assert api.status_code == 200, api.text
    linkedin = await client.post(f"{base}/publications/channels/connect/linkedin", headers=headers)
    assert linkedin.json()["code"] == "plan_upgrade_required"

    from app.domains.billing.service import plan_allows_network

    assert await plan_allows_network(db_session, owner.account.id, "threads")
    assert not await plan_allows_network(db_session, owner.account.id, "tiktok")
    await _with_plan(db_session, owner.account.id, MAX)
    assert await plan_allows_network(db_session, owner.account.id, "tiktok")


async def test_whatsapp_calls_need_a_plan_with_them(multitenant, client, db_session):
    owner, headers = await _owner(db_session, "-calls")
    await _with_plan(db_session, owner.account.id, BASIC)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/calls", json={"conversation_id": 1, "sdp": "v=0 offer sdp"}, headers=headers
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "plan_upgrade_required"
    await _with_plan(db_session, owner.account.id, MAX)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/calls", json={"conversation_id": 1, "sdp": "v=0 offer sdp"}, headers=headers
    )
    assert resp.status_code == 404  # past the plan check: no such conversation


async def test_single_tenant_ignores_plans(client, db_session):
    from app.domains.billing.service import plan_allows_calls, plan_usage_cap

    owner, _ = await _owner(db_session, "-ctc")
    await _with_plan(db_session, owner.account.id, BASIC)
    assert await plan_allows_calls(db_session, owner.account.id)
    assert await plan_usage_cap(db_session, owner.account.id) is None


async def test_the_plan_cap_adds_ai_and_whatsapp_in_usd(multitenant, client, db_session):
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.domains.usage.limits import limit_reached
    from app.domains.usage.models import KIND_AI, UsageRecord, WhatsappCostDay

    owner, headers = await _owner(db_session, "-cap")
    await _with_plan(db_session, owner.account.id, BASIC)  # USD 5
    now = datetime.now(UTC)
    db_session.add(
        UsageRecord(account_id=owner.account.id, kind=KIND_AI, occurred_at=now,
                    category="agent", cost=Decimal("3"), source_id="ai-cap-1")
    )
    day = WhatsappCostDay(
        account_id=owner.account.id, inbox_id=1, day=now.date(), pricing_category="MARKETING",
        pricing_type="REGULAR", country="UY", volume=10, cost=Decimal("2.5"),
        currency="USD", synced_at=now,
    )
    db_session.add(day)
    await db_session.flush()
    assert await limit_reached(db_session, owner.account.id, "ai")
    assert await limit_reached(db_session, owner.account.id, "whatsapp")
    status = (await client.get(f"/api/v1/accounts/{owner.account.id}/billing", headers=headers)).json()
    assert status["usage"] == {"cap": 5.0, "spent": 5.5, "currency": "USD"}

    # Meta billing in another currency: only the AI counts, USD 3 < 5.
    day.currency = "UYU"
    db_session.add(day)
    await db_session.flush()
    assert not await limit_reached(db_session, owner.account.id, "ai")


async def test_metadata_typed_as_text_still_reads(multitenant, client, db_session):
    from app.domains.billing.service import plan_allows_calls, plan_allows_network, plan_usage_cap

    owner, headers = await _owner(db_session, "-text")
    await _with_plan(
        db_session, owner.account.id,
        {"channels": " Meta ", "whatsapp_calls": "TRUE", "usage_cap_usd_cents": "1500"},
    )
    assert await plan_allows_calls(db_session, owner.account.id)
    assert not await plan_allows_network(db_session, owner.account.id, "x")
    assert await plan_usage_cap(db_session, owner.account.id) == Decimal("15.00")
    for bad in ("NaN", "-100", "0", "mucho", True):
        await _with_plan(db_session, owner.account.id, {"usage_cap_usd_cents": bad})
        assert await plan_usage_cap(db_session, owner.account.id) is None, bad
    status = (await client.get(f"/api/v1/accounts/{owner.account.id}/billing", headers=headers)).json()
    assert "usage" not in status
