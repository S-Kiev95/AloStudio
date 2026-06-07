"""Integration tests for the WhatsApp webhook surface.

Covers:
  * Meta verify-token handshake (GET) — echo back hub.challenge or
    401 with the canonical error envelope.
  * Webhook payload receive (POST) — 200 ack, unknown phone -> 404.

The actual ingest (POST -> Message rows) is covered by 5c.3 once
process_cloud_webhook is real. 5c.2 ships a stub so the wiring is
in place + the router 200s correctly when Meta retries.

Anchors:
  reference/chatwoot/app/controllers/webhooks/whatsapp_controller.rb
  reference/chatwoot/app/controllers/concerns/meta_token_verify_concern.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import (
    WHATSAPP_PROVIDER_CLOUD,
    WhatsappChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.main import app

pytestmark = pytest.mark.integration


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


async def _seed_whatsapp_inbox(
    db_session, *, phone_number: str, suffix: str = ""
) -> WhatsappChannel:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@wa-wh.example.com",
            account_name=f"WA Webhook{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA Inbox",
            channel_type="whatsapp",
            channel_params={
                "phone_number": phone_number,
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "EAAxxxx",
                    "phone_number_id": "p1",
                    "business_account_id": "b1",
                    "webhook_verify_token": "secret-token",
                },
            },
        ),
    ).perform()
    assert isinstance(result.channel, WhatsappChannel)
    return result.channel


# ---------------------------------------------------------------------------
# GET — Meta verification handshake
# ---------------------------------------------------------------------------
async def test_verify_returns_challenge_with_correct_token(
    client, db_session
):
    ch = await _seed_whatsapp_inbox(
        db_session, phone_number="+15551112233", suffix="-ok"
    )
    resp = await client.get(
        f"/webhooks/whatsapp/{ch.phone_number}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "secret-token",
            "hub.challenge": "echo-me-back",
        },
    )
    assert resp.status_code == 200
    # Meta accepts JSON-encoded body or raw — we return the JSON form.
    assert resp.json() == "echo-me-back"


async def test_verify_rejects_wrong_token(client, db_session):
    ch = await _seed_whatsapp_inbox(
        db_session, phone_number="+15552223344", suffix="-bad"
    )
    resp = await client.get(
        f"/webhooks/whatsapp/{ch.phone_number}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "1234",
        },
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Error; wrong verify token"}


async def test_verify_rejects_missing_token(client, db_session):
    ch = await _seed_whatsapp_inbox(
        db_session, phone_number="+15553334455", suffix="-notok"
    )
    resp = await client.get(
        f"/webhooks/whatsapp/{ch.phone_number}",
        params={"hub.mode": "subscribe", "hub.challenge": "1234"},
    )
    assert resp.status_code == 401


async def test_verify_unknown_phone_returns_401_like_wrong_token(
    client, db_session
):
    """Mirrors Rails' ``valid_token?`` — unknown phone short-circuits
    to nil, the concern then renders 401 with the canonical envelope.
    Same response as a wrong-token request. Doesn't leak whether the
    phone is registered."""
    await _seed_whatsapp_inbox(
        db_session, phone_number="+15554445566", suffix="-other"
    )
    resp = await client.get(
        "/webhooks/whatsapp/+19999999999",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "secret-token",
            "hub.challenge": "1234",
        },
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Error; wrong verify token"}


# ---------------------------------------------------------------------------
# POST — payload receive
# ---------------------------------------------------------------------------
async def test_receive_200s_for_known_phone(client, db_session):
    ch = await _seed_whatsapp_inbox(
        db_session, phone_number="+15555556677", suffix="-recv"
    )
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "b1",
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5551234567",
                                    "id": "wamid.HBgB...",
                                    "type": "text",
                                    "text": {"body": "hello"},
                                    "timestamp": "1700000000",
                                }
                            ]
                        }
                    }
                ],
            }
        ],
    }
    resp = await client.post(
        f"/webhooks/whatsapp/{ch.phone_number}",
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_receive_unknown_phone_drops_silently(client):
    """Rails ``WhatsappController#process_payload`` doesn't lookup the
    channel before queuing the job — unknown phones get the same 200
    as known ones. We mirror that so Meta doesn't retry on bogus
    payloads."""
    resp = await client.post(
        "/webhooks/whatsapp/+19999999999",
        json={"object": "whatsapp_business_account", "entry": []},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_receive_malformed_json_still_200s(client, db_session):
    """Meta retries on 5xx but accepts any 2xx. A malformed body that
    we can't parse should still get acknowledged so we break the
    retry loop."""
    ch = await _seed_whatsapp_inbox(
        db_session, phone_number="+15556667788", suffix="-malformed"
    )
    resp = await client.post(
        f"/webhooks/whatsapp/{ch.phone_number}",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST — X-Hub-Signature-256 gate (CH-1, opt-in)
# ---------------------------------------------------------------------------
import hashlib  # noqa: E402
import hmac  # noqa: E402

from app.core.config import get_settings  # noqa: E402


@pytest.fixture
def meta_secret():
    """Turn ON per-POST HMAC verification + stamp the signing secret,
    restoring both afterwards (default-OFF tests stay unaffected)."""
    settings = get_settings()
    orig_secret = settings.meta_app_secret
    orig_flag = settings.meta_verify_webhook_signature
    settings.meta_app_secret = "wa-test-secret"
    settings.meta_verify_webhook_signature = True
    try:
        yield "wa-test-secret"
    finally:
        settings.meta_app_secret = orig_secret
        settings.meta_verify_webhook_signature = orig_flag


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()


async def test_receive_valid_signature_passes(
    client, db_session, meta_secret
):
    ch = await _seed_whatsapp_inbox(
        db_session, phone_number="+15557778899", suffix="-sig-ok"
    )
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    resp = await client.post(
        f"/webhooks/whatsapp/{ch.phone_number}",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body, meta_secret),
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_receive_invalid_signature_401(
    client, db_session, meta_secret
):
    ch = await _seed_whatsapp_inbox(
        db_session, phone_number="+15558889900", suffix="-sig-bad"
    )
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    resp = await client.post(
        f"/webhooks/whatsapp/{ch.phone_number}",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Invalid signature"}


async def test_receive_missing_signature_401_when_enabled(
    client, db_session, meta_secret
):
    """Flag ON + no header → reject (the handshake token can't stand in
    for a per-POST signature)."""
    ch = await _seed_whatsapp_inbox(
        db_session, phone_number="+15559990011", suffix="-sig-missing"
    )
    resp = await client.post(
        f"/webhooks/whatsapp/{ch.phone_number}",
        content=b'{"object":"x","entry":[]}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401
