"""Integration tests for the Instagram webhook surface.

Anchors:
  reference/chatwoot/app/controllers/webhooks/instagram_controller.rb
  reference/chatwoot/config/routes.rb (webhooks/instagram routes)
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
def ig_verify_token():
    """Stamp + restore the installation-wide IG verify token."""
    settings = get_settings()
    original = settings.ig_verify_token
    settings.ig_verify_token = "ig-secret"
    try:
        yield "ig-secret"
    finally:
        settings.ig_verify_token = original


# ---------------------------------------------------------------------------
# GET — verification handshake
# ---------------------------------------------------------------------------
async def test_verify_returns_challenge_with_correct_token(
    client, ig_verify_token
):
    resp = await client.get(
        "/webhooks/instagram",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": ig_verify_token,
            "hub.challenge": "echo-me-back",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == "echo-me-back"


async def test_verify_rejects_wrong_token(client, ig_verify_token):
    resp = await client.get(
        "/webhooks/instagram",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "1234",
        },
    )
    assert resp.status_code == 401


async def test_verify_fails_closed_when_setting_empty(client):
    """Default ``ig_verify_token=''`` -> every handshake refuses."""
    settings = get_settings()
    original = settings.ig_verify_token
    settings.ig_verify_token = ""
    try:
        resp = await client.get(
            "/webhooks/instagram",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "",
                "hub.challenge": "1234",
            },
        )
        assert resp.status_code == 401
    finally:
        settings.ig_verify_token = original


# ---------------------------------------------------------------------------
# POST — payload receive
# ---------------------------------------------------------------------------
async def test_receive_200s_for_instagram_payload(client):
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IG-USER-ID",
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": {"id": "USER_PSID"},
                        "recipient": {"id": "IG-USER-ID"},
                        "timestamp": 1700000001,
                        "message": {"mid": "mid.1", "text": "hello"},
                    }
                ],
            }
        ],
    }
    resp = await client.post("/webhooks/instagram", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_receive_rejects_non_instagram_object(client):
    """Mirror Rails: ``object != 'instagram'`` -> 422.

    Important to fail loudly here (not silently 200) so a misrouted
    Messenger payload doesn't get parsed by the IG processor."""
    resp = await client.post(
        "/webhooks/instagram",
        json={"object": "page", "entry": []},
    )
    assert resp.status_code == 422
    assert resp.json() == {"error": "Not an instagram webhook event"}


async def test_receive_object_is_case_insensitive(client):
    """Rails uses ``casecmp(...).zero?`` — accept ``Instagram`` too."""
    resp = await client.post(
        "/webhooks/instagram",
        json={"object": "Instagram", "entry": []},
    )
    assert resp.status_code == 200


async def test_receive_malformed_json_200s(client):
    resp = await client.post(
        "/webhooks/instagram",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
