"""Integration tests for the Facebook Messenger webhook surface.

Covers:
  * Meta verify-token handshake (GET) — installation-wide
    ``settings.fb_verify_token`` is the source of truth, not a
    per-channel column. 401 on mismatch / missing token.
  * Webhook payload receive (POST) — 200 ack regardless of whether
    the page resolves (Rails queues without checking).
  * Empty / unset ``fb_verify_token`` setting refuses every
    handshake (fail-closed).

Anchors:
  reference/chatwoot/config/initializers/facebook_messenger.rb
  reference/chatwoot/app/jobs/webhooks/facebook_events_job.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.db import get_session
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


@pytest.fixture
def fb_verify_token():
    """Stamp + restore the installation-wide verify token between tests.

    The setting is cached via ``@lru_cache``, so we patch the live
    Settings instance directly rather than re-reading the env. The
    teardown restores the original value so other tests see the
    default empty string.
    """
    settings = get_settings()
    original = settings.fb_verify_token
    settings.fb_verify_token = "site-wide-secret"
    try:
        yield "site-wide-secret"
    finally:
        settings.fb_verify_token = original


# ---------------------------------------------------------------------------
# GET — verification handshake
# ---------------------------------------------------------------------------
async def test_verify_returns_challenge_with_correct_token(
    client, fb_verify_token
):
    resp = await client.get(
        "/bot",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": fb_verify_token,
            "hub.challenge": "echo-me-back",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "echo-me-back"


async def test_verify_rejects_wrong_token(client, fb_verify_token):
    resp = await client.get(
        "/bot",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "1234",
        },
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Error; wrong verify token"}


async def test_verify_rejects_missing_token(client, fb_verify_token):
    resp = await client.get(
        "/bot",
        params={"hub.mode": "subscribe", "hub.challenge": "1234"},
    )
    assert resp.status_code == 401


async def test_verify_fails_closed_when_setting_empty(client):
    """Default ``fb_verify_token=''`` -> every handshake refuses.

    This is intentional — without an explicit verify token in
    settings, no Facebook webhook should be accepted (don't leak
    the validation surface)."""
    settings = get_settings()
    original = settings.fb_verify_token
    settings.fb_verify_token = ""
    try:
        resp = await client.get(
            "/bot",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "",
                "hub.challenge": "1234",
            },
        )
        assert resp.status_code == 401
    finally:
        settings.fb_verify_token = original


# ---------------------------------------------------------------------------
# POST — payload receive
# ---------------------------------------------------------------------------
async def test_receive_200s_for_well_formed_payload(client):
    """Any well-formed JSON gets 200 — Rails queues without any
    page-existence check."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "PAGE_ID",
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": {"id": "PSID-1"},
                        "recipient": {"id": "PAGE_ID"},
                        "timestamp": 1700000001,
                        "message": {"mid": "mid.1", "text": "hello"},
                    }
                ],
            }
        ],
    }
    resp = await client.post("/bot", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_receive_200s_for_unknown_page(client):
    """Even with no FB pages registered we ack 200 — the processor
    drops unknown pages internally."""
    resp = await client.post(
        "/bot",
        json={"object": "page", "entry": []},
    )
    assert resp.status_code == 200


async def test_receive_malformed_json_still_200s(client):
    """Meta retries on 5xx; malformed body still acks so we break the
    retry loop."""
    resp = await client.post(
        "/bot",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200


async def test_receive_non_object_payload_still_200s(client):
    """A JSON array / string / number isn't a Meta payload — drop
    silently with 200."""
    resp = await client.post(
        "/bot", json=["not", "an", "object"]
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST — X-Hub-Signature-256 gate (CH-1, opt-in)
# ---------------------------------------------------------------------------
import hashlib  # noqa: E402
import hmac  # noqa: E402


@pytest.fixture
def meta_secret():
    """Turn ON per-POST HMAC verification + stamp the signing secret,
    restoring both afterwards."""
    settings = get_settings()
    orig_secret = settings.meta_app_secret
    orig_flag = settings.meta_verify_webhook_signature
    settings.meta_app_secret = "fb-test-secret"
    settings.meta_verify_webhook_signature = True
    try:
        yield "fb-test-secret"
    finally:
        settings.meta_app_secret = orig_secret
        settings.meta_verify_webhook_signature = orig_flag


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()


async def test_receive_valid_signature_passes(client, meta_secret):
    body = b'{"object":"page","entry":[]}'
    resp = await client.post(
        "/bot",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body, meta_secret),
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_receive_invalid_signature_401(client, meta_secret):
    body = b'{"object":"page","entry":[]}'
    resp = await client.post(
        "/bot",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Invalid signature"}


async def test_receive_missing_signature_401_when_enabled(
    client, meta_secret
):
    resp = await client.post(
        "/bot",
        content=b'{"object":"page","entry":[]}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401
