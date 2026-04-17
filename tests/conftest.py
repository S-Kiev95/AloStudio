"""Global fixtures for AloStudio tests.

We keep three test tiers — matching the pytest markers:
  unit         — no IO, no DB. Pure function tests.
  integration  — real Postgres + Redis (testcontainers). App wired normally.
  parity       — spins up AloStudio in-process AND requires the reference
                 Chatwoot Docker stack reachable at CHATWOOT_REF_BASE_URL.
                 Tests skip automatically if the reference is unreachable.

Fixtures are defined here at the top level so they are available in every
subdirectory.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager

# Force test env before the app imports its settings.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-please-override-in-prod")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://alostudio:alostudio@localhost:5433/alostudio_test",
    ),
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql+psycopg://alostudio:alostudio@localhost:5433/alostudio_test",
    ),
)
os.environ.setdefault("REDIS_URL", os.environ.get("REDIS_URL", "redis://localhost:6380/15"))
os.environ.setdefault(
    "ARQ_REDIS_URL", os.environ.get("ARQ_REDIS_URL", "redis://localhost:6380/14")
)


@pytest.fixture
async def alo_app():
    """In-process FastAPI app with lifespan management."""
    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def alo_client(alo_app) -> AsyncIterator[httpx.AsyncClient]:
    """httpx client talking to the in-process FastAPI app via ASGI transport."""
    transport = httpx.ASGITransport(app=alo_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
