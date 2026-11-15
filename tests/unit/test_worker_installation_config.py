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


@pytest.mark.asyncio
async def test_each_job_picks_up_settings_saved_after_startup(monkeypatch):
    # A key loaded from the dashboard while the worker runs must reach it
    # without a restart.
    calls = []

    async def refresh(session):
        calls.append(session)
        return True

    monkeypatch.setattr(service, "refresh_if_stale", refresh)
    await WorkerSettings.on_job_start({"job_id": "x"})
    await WorkerSettings.on_job_start({"job_id": "y"})
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_a_failed_refresh_does_not_stop_the_job(monkeypatch):
    async def refresh(session):
        raise ConnectionError("db down")

    monkeypatch.setattr(service, "refresh_if_stale", refresh)
    await WorkerSettings.on_job_start({"job_id": "x"})
