"""The worker reads the settings stored in Ajustes → Instalación too: without
them, renewing a network's token fails and the channel asks to reconnect."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domains.installation import service
from app.workers.scheduler import WorkerSettings


async def _start(monkeypatch, apply) -> dict:
    monkeypatch.setattr(service, "apply_overlay", apply)
    ctx: dict = {}
    await WorkerSettings.on_startup(ctx)
    assert isinstance(ctx["engine"], AsyncEngine)
    await ctx["engine"].dispose()
    return ctx


@pytest.mark.asyncio
async def test_startup_loads_the_installation_settings(monkeypatch):
    calls = []

    async def apply(session):
        calls.append(session)
        return {}

    await _start(monkeypatch, apply)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_a_database_that_is_not_up_does_not_stop_the_worker(monkeypatch):
    async def apply(session):
        raise ConnectionError("db down")

    await _start(monkeypatch, apply)
