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
from datetime import timedelta
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

    for status, code in (("trialing", 200), ("active", 200), ("unpaid", 402), ("canceled", 402)):
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


async def test_the_plan_cap_is_ai_only_and_credit_extends_it(multitenant, client, db_session):
    from datetime import UTC, datetime

    from app.domains.usage.limits import limit_reached
    from app.domains.usage.models import KIND_AI, UsageRecord, WhatsappCostDay

    owner, headers = await _owner(db_session, "-cap")
    account_id = owner.account.id
    await _with_plan(db_session, account_id, BASIC)  # USD 5 of AI
    now = datetime.now(UTC)
    db_session.add(
        UsageRecord(account_id=account_id, kind=KIND_AI, occurred_at=now,
                    category="agent", cost=Decimal("6"), source_id="ai-cap-1")
    )
    db_session.add(
        WhatsappCostDay(
            account_id=account_id, inbox_id=1, day=now.date(), pricing_category="MARKETING",
            pricing_type="REGULAR", country="UY", volume=10, cost=Decimal("50"),
            currency="USD", synced_at=now,
        )
    )
    await db_session.flush()
    # WhatsApp is the client's own bill with Meta: the plan never stops it.
    assert not await limit_reached(db_session, account_id, "whatsapp")
    assert await limit_reached(db_session, account_id, "ai")

    # USD 20 of credit gives USD 10; the USD 1 past the cap is taken from it.
    paid = {
        "type": "order.paid",
        "data": {
            "id": "ord_credit_1",
            "paid": True,
            "net_amount": 2000,
            "refunded_amount": 0,
            "created_at": now.isoformat(),
            "product": {"id": "prod_credits", "metadata": {"kind": "ai_credits"}},
            "customer": {"id": "cus_c", "external_id": str(account_id)},
            "metadata": {"account_id": str(account_id)},
        },
    }
    assert (await _post(client, paid, "wh_credit_1")).status_code == 202
    assert (await _post(client, paid, "wh_credit_1b")).status_code == 202  # same order again
    assert not await limit_reached(db_session, account_id, "ai")
    status = (await client.get(f"/api/v1/accounts/{account_id}/billing", headers=headers)).json()
    assert status["usage"] == {"cap": 5.0, "spent": 6.0, "currency": "USD", "credit_balance": 9.0}
    credits = (await client.get(f"/api/v1/accounts/{account_id}/billing/credits", headers=headers)).json()
    assert credits["balance"] == 9.0
    [purchase] = credits["purchases"]
    assert {k: purchase[k] for k in ("paid", "credit", "refunded")} == {
        "paid": 20.0, "credit": 10.0, "refunded": False,
    }

    # A full refund takes the credit back: AI stops again.
    refunded = {**paid, "type": "order.refunded", "data": {**paid["data"], "refunded_amount": 2000}}
    await _post(client, refunded, "wh_credit_2")
    assert await limit_reached(db_session, account_id, "ai")


def test_credit_tiers():
    from app.domains.billing.service import credit_for

    assert credit_for(499) == 0
    assert credit_for(500) == Decimal("2.50")
    assert credit_for(4900) == Decimal("24.50")
    assert credit_for(5000) == Decimal("32.50")
    assert credit_for(10_000) == Decimal("75.00")
    assert credit_for(20_000) == Decimal("150.00")
    assert credit_for(501) == Decimal("2.51")  # 2.505: half a cent up, like the screen


async def test_credits_checkout_sends_the_amount(client, db_session):
    owner, headers = await _owner(db_session, "-buy")
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{SANDBOX}/products/").mock(
            return_value=httpx.Response(200, json={"items": [
                {"id": "prod_other", "metadata": {}},
                {"id": "prod_credits", "metadata": {"kind": "ai_credits"}},
            ]})
        )
        checkout = mock.post(f"{SANDBOX}/checkouts/").mock(
            return_value=httpx.Response(201, json={"url": "https://sandbox.polar.sh/checkout/cr"})
        )
        base = f"/api/v1/accounts/{owner.account.id}/billing/credits/checkout"
        too_little = await client.post(base, json={"amount": 4.99}, headers=headers)
        assert too_little.status_code == 422
        resp = await client.post(base, json={"amount": 50}, headers=headers)
    assert resp.json() == {"url": "https://sandbox.polar.sh/checkout/cr"}
    sent = json.loads(checkout.calls.last.request.content)
    assert sent["products"] == ["prod_credits"]
    assert sent["amount"] == 5000
    assert sent["metadata"] == {"account_id": str(owner.account.id)}


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


async def _credit(client, account_id: int, order_id: str, cents: int, paid_at) -> None:
    payload = {
        "type": "order.paid",
        "data": {
            "id": order_id, "paid": True, "net_amount": cents, "refunded_amount": 0,
            "created_at": paid_at.isoformat(),
            "product": {"id": "prod_credits", "metadata": {"kind": "ai_credits"}},
            "customer": {"id": "cus_x", "external_id": str(account_id)},
            "metadata": {"account_id": str(account_id)},
        },
    }
    assert (await _post(client, payload, f"wh_{order_id}")).status_code == 202


async def test_credit_pays_only_what_came_after_buying_it(multitenant, client, db_session):
    from datetime import UTC, datetime, timedelta

    from app.domains.usage.limits import credit_balance
    from app.domains.usage.models import KIND_AI, UsageRecord

    owner, _ = await _owner(db_session, "-after")
    account_id = owner.account.id
    await _with_plan(db_session, account_id, BASIC)  # USD 5
    now = datetime.now(UTC)
    # USD 7 before buying (2 over the cap, while AI was stopped) ...
    db_session.add(UsageRecord(account_id=account_id, kind=KIND_AI, occurred_at=now - timedelta(minutes=5),
                               category="agent", cost=Decimal("7"), source_id="after-1"))
    await db_session.flush()
    await _credit(client, account_id, "ord_after", 2000, now - timedelta(minutes=1))  # USD 10
    # ... and USD 3 after: only those come out of the credit.
    db_session.add(UsageRecord(account_id=account_id, kind=KIND_AI, occurred_at=now,
                               category="agent", cost=Decimal("3"), source_id="after-2"))
    await db_session.flush()
    assert await credit_balance(db_session, account_id) == Decimal("7")


async def test_a_closed_month_keeps_its_credit_after_a_plan_change(multitenant, client, db_session):
    from datetime import UTC, datetime

    from app.domains.billing.models import CreditMonthUsage
    from app.domains.usage.limits import credit_balance
    from app.domains.usage.models import KIND_AI, UsageRecord

    owner, _ = await _owner(db_session, "-frozen")
    account_id = owner.account.id
    await _with_plan(db_session, account_id, MAX)  # USD 40
    last_month = (datetime.now(UTC).replace(day=1) - timedelta(days=1)).replace(day=10)
    await _credit(client, account_id, "ord_frozen", 2000, last_month)  # USD 10
    db_session.add(UsageRecord(account_id=account_id, kind=KIND_AI, occurred_at=last_month.replace(day=20),
                               category="agent", cost=Decimal("42"), source_id="frozen-1"))
    await db_session.flush()
    assert await credit_balance(db_session, account_id) == Decimal("8")  # 2 over Max's 40
    rows = (await db_session.exec(select(CreditMonthUsage).where(CreditMonthUsage.account_id == account_id))).all()
    assert [r.used for r in rows] == [Decimal("2")]
    # Down to Basic (USD 5): last month stays as it was charged.
    await _with_plan(db_session, account_id, BASIC)
    assert await credit_balance(db_session, account_id) == Decimal("8")


async def test_an_order_without_product_stays_to_replay(client, db_session):
    owner, _ = await _owner(db_session, "-noprod")
    payload = {"type": "order.paid", "data": {"id": "ord_noprod", "paid": True, "net_amount": 2000,
               "metadata": {"account_id": str(owner.account.id)}}}
    assert (await _post(client, payload, "wh_noprod")).status_code == 202
    event = (await db_session.exec(select(BillingEvent).where(BillingEvent.webhook_id == "wh_noprod"))).one()
    assert event.processed_at is None
    assert "without product" in (event.error or "")


async def _spend_ai(db_session, account_id: int, cost: str, source_id: str) -> None:
    from datetime import UTC, datetime

    from app.domains.usage.models import KIND_AI, UsageRecord

    db_session.add(
        UsageRecord(account_id=account_id, kind=KIND_AI, occurred_at=datetime.now(UTC),
                    category="agent", cost=Decimal(cost), source_id=source_id)
    )
    await db_session.flush()


async def test_the_plan_cap_tells_the_admins_at_80_and_100(multitenant, client, db_session):
    from app.domains.notifications.mailer import build_notification_email
    from app.domains.notifications.models import Notification
    from app.domains.usage.limits import notify_limits

    owner, _ = await _owner(db_session, "-alert")
    account_id = owner.account.id
    await _with_plan(db_session, account_id, BASIC)  # USD 5 of AI

    await _spend_ai(db_session, account_id, "3", "ai-alert-1")  # 60 %
    assert await notify_limits(db_session) == []

    await _spend_ai(db_session, account_id, "1.5", "ai-alert-2")  # 90 %
    [first] = await notify_limits(db_session)
    note = await db_session.get(Notification, first)
    assert note is not None and note.user_id == owner.user.id
    assert note.primary_actor_type == "AccountSubscription"
    assert note.meta["level"] == 80 and note.meta["source"] == "plan"
    assert "4.50 / 5.00" in note.meta["title"]
    # Once per level and month.
    assert await notify_limits(db_session) == []

    await _spend_ai(db_session, account_id, "1", "ai-alert-3")  # 110 %
    [second] = await notify_limits(db_session)
    note = await db_session.get(Notification, second)
    assert note is not None and note.meta["level"] == 100
    # The mail says credit keeps the AI going, and leads to Facturación.
    mail = build_notification_email(notification=note, user=owner.user, conversation=None)
    body = mail.get_content()
    assert "/settings/billing" in body
    assert "credit" in body.lower() or "crédito" in body.lower()
    assert await notify_limits(db_session) == []


async def test_a_single_tenant_install_has_no_plan_cap_alerts(client, db_session):
    from app.domains.usage.limits import notify_limits

    owner, _ = await _owner(db_session, "-noalert")
    await _with_plan(db_session, owner.account.id, BASIC)
    await _spend_ai(db_session, owner.account.id, "9", "ai-noalert-1")
    assert await notify_limits(db_session) == []


async def test_the_admins_hear_when_the_ai_credit_runs_low_and_out(multitenant, client, db_session):
    from datetime import UTC, datetime

    from app.domains.notifications.models import Notification
    from app.domains.usage.limits import notify_limits

    owner, _ = await _owner(db_session, "-credit")
    account_id = owner.account.id
    await _with_plan(db_session, account_id, BASIC)  # USD 5 of AI
    now = datetime.now(UTC)
    order = {
        "type": "order.paid",
        "data": {
            "id": "ord_low_1", "paid": True, "net_amount": 2000, "refunded_amount": 0,
            "created_at": now.isoformat(),
            "product": {"id": "prod_credits", "metadata": {"kind": "ai_credits"}},
            "customer": {"id": "cus_low", "external_id": str(account_id)},
            "metadata": {"account_id": str(account_id)},
        },
    }
    assert (await _post(client, order, "wh_low_1")).status_code == 202  # USD 10 of credit

    def sources(notes):
        return sorted((n.meta["source"], n.meta["level"]) for n in notes)

    async def alerts():
        return [await db_session.get(Notification, i) for i in await notify_limits(db_session)]

    # USD 13 of AI: 8 past the cap, USD 2 of credit left (under 20 % of 10).
    await _spend_ai(db_session, account_id, "13", "ai-low-1")
    assert ("credit", 20) in sources(await alerts())
    assert all(n.meta["source"] != "credit" for n in await alerts())  # once

    await _spend_ai(db_session, account_id, "3", "ai-low-2")  # used up
    notes = [n for n in await alerts() if n.meta["source"] == "credit"]
    assert sources(notes) == [("credit", 100)]
    assert "0.00 USD" in notes[0].meta["title"]


async def test_an_unusual_day_of_ai_spend_is_reported_once(multitenant, client, db_session):
    from datetime import UTC, datetime, timedelta

    from app.domains.notifications.models import Notification
    from app.domains.usage.limits import notify_limits
    from app.domains.usage.models import KIND_AI, UsageRecord

    owner, _ = await _owner(db_session, "-spike")
    account_id = owner.account.id
    await _with_plan(db_session, account_id, MAX)  # USD 40: no cap alert here
    now = datetime.now(UTC)
    for day in range(1, 8):  # USD 0.20 a day for a week
        db_session.add(
            UsageRecord(account_id=account_id, kind=KIND_AI, occurred_at=now - timedelta(days=day),
                        category="agent", cost=Decimal("0.20"), source_id=f"ai-spike-old-{day}")
        )
    await db_session.flush()
    await _spend_ai(db_session, account_id, "0.50", "ai-spike-1")
    assert await notify_limits(db_session) == []  # under USD 1: no news

    await _spend_ai(db_session, account_id, "2", "ai-spike-2")
    [spike] = await notify_limits(db_session)
    note = await db_session.get(Notification, spike)
    assert note is not None and note.meta["source"] == "spike"
    assert "2.50 USD" in note.meta["title"]
    await _spend_ai(db_session, account_id, "5", "ai-spike-3")
    assert await notify_limits(db_session) == []  # once a day


async def test_the_status_says_what_the_plan_includes(multitenant, client, db_session):
    owner, headers = await _owner(db_session, "-allows")
    url = f"/api/v1/accounts/{owner.account.id}/billing"
    await _with_plan(db_session, owner.account.id, BASIC)
    allows = (await client.get(url, headers=headers)).json()["allows"]
    assert "telegram" not in allows["inbox_channels"] and "whatsapp" in allows["inbox_channels"]
    assert allows["networks"] == ["facebook_page", "instagram", "threads"]
    assert allows["whatsapp_calls"] is False
    await _with_plan(db_session, owner.account.id, MAX)
    allows = (await client.get(url, headers=headers)).json()["allows"]
    assert allows == {"inbox_channels": None, "networks": None, "whatsapp_calls": True}


async def test_a_single_tenant_install_includes_everything(client, db_session):
    owner, headers = await _owner(db_session, "-allows-st")
    await _with_plan(db_session, owner.account.id, BASIC)
    allows = (await client.get(f"/api/v1/accounts/{owner.account.id}/billing", headers=headers)).json()["allows"]
    assert allows == {"inbox_channels": None, "networks": None, "whatsapp_calls": True}


async def test_one_free_trial_per_account(client, db_session):
    owner, headers = await _owner(db_session, "-trial")
    account_id = owner.account.id
    base = f"/api/v1/accounts/{account_id}/billing"
    trialing = {
        "type": "subscription.created",
        "data": {
            "id": "sub_trial_1", "status": "trialing", "product_id": "prod_basic",
            "product": {"id": "prod_basic", "name": "Basic", "metadata": {}},
            "customer": {"id": "cus_t", "external_id": str(account_id)},
            "metadata": {"account_id": str(account_id)},
        },
    }
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{SANDBOX}/products/").mock(
            return_value=httpx.Response(200, json={"items": [
                {"id": "prod_basic", "name": "Basic", "recurring_interval": "month",
                 "trial_interval": "day", "trial_interval_count": 30,
                 "prices": [{"price_amount": 1000, "price_currency": "usd"}]},
            ]})
        )
        checkout = mock.post(f"{SANDBOX}/checkouts/").mock(
            return_value=httpx.Response(201, json={"url": "https://sandbox.polar.sh/checkout/t"})
        )
        # Before: the trial is offered and the checkout keeps it.
        plans = (await client.get(f"{base}/plans", headers=headers)).json()["plans"]
        assert plans[0]["trial_days"] == 30
        await client.post(f"{base}/checkout", json={"product_id": "prod_basic"}, headers=headers)
        assert "allow_trial" not in json.loads(checkout.calls.last.request.content)

        # It had its trial, then canceled: no second one.
        assert (await _post(client, trialing, "wh_trial_1")).status_code == 202
        canceled = {**trialing, "type": "subscription.canceled",
                    "data": {**trialing["data"], "status": "canceled"}}
        assert (await _post(client, canceled, "wh_trial_2")).status_code == 202
        plans = (await client.get(f"{base}/plans", headers=headers)).json()["plans"]
        assert plans[0]["trial_days"] is None
        await client.post(f"{base}/checkout", json={"product_id": "prod_basic"}, headers=headers)
        assert json.loads(checkout.calls.last.request.content)["allow_trial"] is False


def _sub_event(account_id: int, kind: str, status: str, **extra) -> dict:
    return {
        "type": kind,
        "data": {
            "id": "sub_renew_1", "status": status, "product_id": "prod_basic",
            "product": {"id": "prod_basic", "name": "Basic", "metadata": {}},
            "customer": {"id": "cus_r", "external_id": str(account_id)},
            "metadata": {"account_id": str(account_id)},
            **extra,
        },
    }


async def test_a_renewal_moves_the_period_forward(multitenant, client, db_session):
    owner, headers = await _owner(db_session, "-renew")
    account_id = owner.account.id
    first = "2026-12-01T00:00:00Z"
    second = "2027-01-01T00:00:00Z"
    await _post(client, _sub_event(account_id, "subscription.active", "active", current_period_end=first), "wh_r1")
    # Polar renews: same subscription, next cycle.
    await _post(client, _sub_event(account_id, "subscription.updated", "active", current_period_end=second), "wh_r2")
    status = (await client.get(f"/api/v1/accounts/{account_id}/billing", headers=headers)).json()
    assert status["has_access"] is True and status["access_until"] is None
    assert status["current_period_end"] == 1798761600  # 2027-01-01


async def test_a_failed_renewal_keeps_the_account_open_seven_days(multitenant, client, db_session):
    from datetime import UTC, datetime, timedelta

    owner, headers = await _owner(db_session, "-pastdue")
    account_id = owner.account.id
    url = f"/api/v1/accounts/{account_id}/billing"
    await _post(client, _sub_event(account_id, "subscription.active", "active"), "wh_p1")

    # The charge failed today: open, with the date to fix it by.
    failed = datetime.now(UTC) - timedelta(hours=1)
    await _post(client, _sub_event(account_id, "subscription.updated", "past_due",
                                   past_due_at=failed.isoformat()), "wh_p2")
    status = (await client.get(url, headers=headers)).json()
    assert status["status"] == "past_due" and status["has_access"] is True
    assert status["access_until"] == int((failed + timedelta(days=7)).timestamp())

    # Eight days after the failure: closed (402), billing still reachable.
    late = datetime.now(UTC) - timedelta(days=8)
    await _post(client, _sub_event(account_id, "subscription.updated", "past_due",
                                   past_due_at=late.isoformat()), "wh_p3")
    assert (await client.get(f"/api/v1/accounts/{account_id}/labels", headers=headers)).status_code == 402
    assert (await client.get(url, headers=headers)).json()["has_access"] is False

    # The card was updated and Polar charged it: open again, no date.
    await _post(client, _sub_event(account_id, "subscription.updated", "active"), "wh_p4")
    status = (await client.get(url, headers=headers)).json()
    assert status["has_access"] is True and status["access_until"] is None
