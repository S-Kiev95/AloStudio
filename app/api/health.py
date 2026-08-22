"""Health + root endpoints.

``/health`` returns a live-component snapshot the deployment's
load balancer can probe. ``/`` echoes Chatwoot's stripped JSON
status payload.

Phase 10.3 beefs up ``/health`` with:
  * ``database`` — runs ``SELECT 1`` against the active session.
  * ``redis``    — pings the realtime broadcaster (also the cache /
                   pub-sub backbone).
  * ``uptime``   — seconds since app start.
  * ``version``  — pinned to ``0.0.1`` + ``settings.app_env``.
  * ``commit``   — the git revision this process is running.
  * ``started_at`` — when it started, so a deploy can be verified.

The endpoint always returns 200 with the live status — components
failing show ``"down"`` in their slot rather than 5xx-ing the whole
probe (mirrors Chatwoot's tolerant healthcheck stance).
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis_lib
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.version import short_commit

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict[str, str]:
    """Chatwoot returns a JSON object at `/` with version info — mirror that shape."""
    return {
        "version": "0.0.1",
        "timestamp": "",
        "queue_services": "ok",
        "data_services": "ok",
    }


@router.get("/health")
async def health(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Liveness + dependency status.

    Always 200 — individual components show ``"up"``/``"down"`` so
    load-balancer + dashboard alerting can distinguish "the app
    process is alive" from "DB is reachable"."""
    settings = get_settings()

    # ----- database -----
    db_status = "down"
    db_error: str | None = None
    try:
        # ``session.exec`` (SQLModel) instead of ``session.execute``
        # (raw SQLAlchemy) — the latter emits a SQLModel DeprecationWarning.
        await session.exec(text("SELECT 1"))
        db_status = "up"
    except Exception as exc:  # noqa: BLE001
        db_error = type(exc).__name__

    # ----- redis -----
    redis_status = "down"
    redis_error: str | None = None
    client: redis_lib.Redis | None = None
    try:
        client = redis_lib.from_url(settings.redis_url)
        await client.ping()
        redis_status = "up"
    except Exception as exc:  # noqa: BLE001
        redis_error = type(exc).__name__
    finally:
        if client is not None:
            # Closing a probe client is best-effort — never let it mask the
            # health result we just computed.
            with suppress(Exception):
                await client.aclose()

    # ----- uptime -----
    started_at = getattr(request.app.state, "started_at", None)
    uptime_seconds = (
        int((datetime.now(UTC) - started_at).total_seconds())
        if started_at is not None
        else 0
    )

    overall = (
        "ok" if db_status == "up" and redis_status == "up" else "degraded"
    )
    return {
        "status": overall,
        "version": "0.0.1",
        # The revision this process loaded, and when it loaded it.
        # Together they answer "did my deploy take?" without inferring it
        # from a git pull in another terminal. None is legitimate — a
        # source tarball has no .git — and must not break the probe.
        "commit": short_commit(),
        "started_at": started_at.isoformat() if started_at else None,
        "env": settings.app_env,
        "uptime_seconds": uptime_seconds,
        "components": {
            "database": {"status": db_status, "error": db_error},
            "redis": {"status": redis_status, "error": redis_error},
        },
    }
