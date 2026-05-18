"""Integration tests for the Phase 10.3 observability layer.

Covers:
  * RequestIdMiddleware — reads incoming ``X-Request-Id``, mints when
    missing, always echoes on the response.
  * ``/health`` payload — components map with up/down per dependency.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

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


# ---------------------------------------------------------------------------
# Request-id middleware
# ---------------------------------------------------------------------------
async def test_request_id_echoes_incoming_header(client):
    incoming = "deadbeef-1234-cafe-abcd-deadbeefcafe"
    resp = await client.get("/", headers={"X-Request-Id": incoming})
    assert resp.status_code == 200
    assert resp.headers["X-Request-Id"] == incoming


async def test_request_id_minted_when_missing(client):
    """No incoming header → middleware mints a UUID and echoes it."""
    resp = await client.get("/")
    assert resp.status_code == 200
    sent = resp.headers.get("X-Request-Id", "")
    # UUID4 string with hyphens — 36 chars.
    assert len(sent) == 36
    assert sent.count("-") == 4


async def test_request_id_persists_across_consecutive_requests(client):
    """Each request gets its own id — no leak from prior request."""
    a = (await client.get("/")).headers["X-Request-Id"]
    b = (await client.get("/")).headers["X-Request-Id"]
    assert a != b


async def test_request_id_ignored_when_too_long(client):
    """Caller can't poison the contextvar with a 5KB string —
    middleware mints a fresh UUID when the input is unsane."""
    bogus = "x" * 10_000
    resp = await client.get("/", headers={"X-Request-Id": bogus})
    sent = resp.headers["X-Request-Id"]
    assert sent != bogus
    assert len(sent) == 36


# ---------------------------------------------------------------------------
# Health payload
# ---------------------------------------------------------------------------
async def test_health_payload_shape(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    # Top-level keys.
    assert body["status"] in {"ok", "degraded"}
    assert body["version"] == "0.0.1"
    assert "uptime_seconds" in body
    assert isinstance(body["uptime_seconds"], int)
    # Component map.
    components = body["components"]
    assert "database" in components
    assert "redis" in components
    assert components["database"]["status"] in {"up", "down"}
    assert components["redis"]["status"] in {"up", "down"}


async def test_health_reports_database_up(client):
    """The test fixture provides a real DB session — health should
    report it as up."""
    resp = await client.get("/health")
    body = resp.json()
    assert body["components"]["database"]["status"] == "up"
    assert body["components"]["database"]["error"] is None
