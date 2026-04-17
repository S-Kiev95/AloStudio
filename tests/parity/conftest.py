"""Parity-tier fixtures.

Every parity test gets two httpx clients:

    alo_client  — already provided by tests/conftest.py (in-process FastAPI)
    cw_client   — reaches the Chatwoot Rails reference at CHATWOOT_REF_BASE_URL

If the Chatwoot reference is not reachable, parity tests are SKIPPED (not
failed) so the unit/integration tiers stay green on dev machines that have not
booted the reference stack.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from app.core.config import get_settings


@pytest.fixture(scope="session")
def chatwoot_base_url() -> str:
    return get_settings().chatwoot_ref_base_url


@pytest.fixture(scope="session")
async def _chatwoot_reachable(chatwoot_base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(base_url=chatwoot_base_url, timeout=2.0) as c:
            r = await c.get("/")
            return r.status_code < 500
    except httpx.HTTPError:
        return False


@pytest.fixture
async def cw_client(
    chatwoot_base_url: str, _chatwoot_reachable: bool
) -> AsyncIterator[httpx.AsyncClient]:
    if not _chatwoot_reachable:
        pytest.skip(
            f"Chatwoot reference not reachable at {chatwoot_base_url}. "
            f"Start it with: docker compose --profile reference up -d"
        )
    async with httpx.AsyncClient(base_url=chatwoot_base_url, timeout=10.0) as client:
        yield client
