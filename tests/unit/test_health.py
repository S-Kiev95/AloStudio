"""Smoke test: FastAPI app boots and serves its health endpoint.

Does NOT hit the DB — root / only returns a static payload, /health is tested in
the integration tier where Postgres is available.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


async def test_root_returns_version(alo_client) -> None:
    r = await alo_client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
