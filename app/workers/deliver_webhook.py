"""ARQ-backed webhook + agent-bot delivery (v2.9).

Three concerns, three layers:

  * :func:`deliver_webhook_now` — pure delivery logic. Takes the
    already-built body + receiver metadata, POSTs, returns a
    :class:`DeliveryOutcome`. Tests drive this directly with respx so
    they exercise the retry decision without booting an ARQ worker.

  * :func:`deliver_webhook_task` — the ARQ task wrapper. Calls the
    logic; on a transient outcome raises ``arq.Retry(defer=...)`` with
    the schedule below; on terminal-fail writes a dead-letter row.

  * :func:`enqueue_delivery` — the listener-facing entry point.
    Enqueues the ARQ task; falls back to an inline call when no ARQ
    pool is reachable (mirrors :mod:`app.workers.instagram` so the
    dev/test surface stays usable without a worker process).

Backoff schedule mirrors Chatwoot's ``WebhookJob``::

    attempt | wait next |
    --------+-----------+
       1    |    5 s    |
       2    |   30 s    |
       3    |    5 min  |
       4    |   30 min  |
       5    | dead-letter — give up

5 total attempts (= ``MAX_ATTEMPTS``): the initial try + 4 retries at
the waits above; attempt 5's failure writes the quarantine row instead
of deferring again. ARQ's ``ctx['job_try']`` is 1-indexed, which
matches the attempt counter above.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.webhooks.models import (
    RECEIVER_KIND_AGENT_BOT,
    RECEIVER_KIND_WEBHOOK,
    WebhookDeadLetter,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schedule + caps
# ---------------------------------------------------------------------------
#: Mirrors Chatwoot's ``WebhookJob`` retry config. Indexed by the
#: ``attempt`` number that just finished (1 = the first try) → seconds
#: until the next try fires. ``None`` means no more retries → dead-letter.
BACKOFF_SECONDS: dict[int, int | None] = {
    1: 5,
    2: 30,
    3: 5 * 60,
    4: 30 * 60,
    5: None,
}

#: How many attempts before we quarantine. 5 total attempts: the
#: initial try + 4 retries (5s / 30s / 5min / 30min). On attempt 5 the
#: ``attempt < MAX_ATTEMPTS`` guard is False, so it dead-letters instead
#: of deferring — i.e. the 30-min tier (attempt 4 → wait) IS exercised.
MAX_ATTEMPTS = 5

#: HTTP timeout per attempt. Matches the pre-v2.9 inline delivery
#: timeout so receivers that were just slow (not 5xx) get the same
#: window — moving to background doesn't change "what's too slow".
HTTP_TIMEOUT_SECONDS = 10.0


# ---------------------------------------------------------------------------
# Outcome types
# ---------------------------------------------------------------------------
OutcomeKind = Literal["ok", "retry", "dead_letter"]


@dataclass
class DeliveryOutcome:
    """What :func:`deliver_webhook_now` decided.

    ``kind`` drives what the ARQ wrapper does next:

      * ``ok``         — 2xx response; nothing to do.
      * ``retry``      — non-2xx or transport error AND attempts left;
                         caller raises ``arq.Retry(defer=...)`` based on
                         :attr:`next_backoff_seconds`.
      * ``dead_letter`` — non-2xx or transport error AND no attempts
                         left; caller writes the quarantine row.
    """

    kind: OutcomeKind
    status_code: int | None
    error: str | None
    next_backoff_seconds: int | None


# ---------------------------------------------------------------------------
# HMAC helpers — same digest the inline path used, kept identical so
# receivers don't see signature churn when this lands.
# ---------------------------------------------------------------------------
def _sign(body_bytes: bytes, secret: str | None) -> str:
    if not secret:
        return ""
    return hmac.new(
        secret.encode("utf-8"), body_bytes, hashlib.sha256
    ).hexdigest()


def build_headers(body_bytes: bytes, secret: str | None, event_id: str) -> dict[str, str]:
    """Standard outbound headers — kept here so the inline fallback +
    the ARQ wrapper + the listener tests all produce the same bytes."""
    signature = _sign(body_bytes, secret)
    return {
        "Content-Type": "application/json",
        "X-Chatwoot-Delivery": event_id,
        # Legacy Chatwoot-parity bare-hex header.
        "X-Chatwoot-Signature": signature,
        # v2.7 modern alias (GitHub-style).
        "X-AloStudio-Signature": f"sha256={signature}" if signature else "",
    }


# ---------------------------------------------------------------------------
# Pure delivery logic — testable without ARQ
# ---------------------------------------------------------------------------
async def deliver_webhook_now(
    *,
    url: str,
    body: dict[str, Any],
    secret: str | None,
    attempt: int,
) -> DeliveryOutcome:
    """POST the body once and decide what should happen next.

    Pure — does NOT touch the database. The ARQ wrapper persists the
    dead-letter row when this returns ``dead_letter`` so the layering
    stays clean for tests.
    """
    body_bytes = json.dumps(body).encode("utf-8")
    event_id = str(body.get("event_id") or uuid.uuid4())
    headers = build_headers(body_bytes, secret, event_id)

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, content=body_bytes, headers=headers)
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        return _failure_outcome(
            attempt=attempt, status_code=None, error=str(exc) or type(exc).__name__
        )

    if 200 <= resp.status_code < 300:
        return DeliveryOutcome(
            kind="ok",
            status_code=resp.status_code,
            error=None,
            next_backoff_seconds=None,
        )

    # Non-2xx: failure path.
    return _failure_outcome(
        attempt=attempt,
        status_code=resp.status_code,
        error=resp.text[:500] if resp.text else None,
    )


def _failure_outcome(
    *, attempt: int, status_code: int | None, error: str | None
) -> DeliveryOutcome:
    """Map ``attempt`` (1-indexed) to ``retry`` or ``dead_letter``."""
    next_backoff = BACKOFF_SECONDS.get(attempt)
    if attempt < MAX_ATTEMPTS and next_backoff is not None:
        return DeliveryOutcome(
            kind="retry",
            status_code=status_code,
            error=error,
            next_backoff_seconds=next_backoff,
        )
    return DeliveryOutcome(
        kind="dead_letter",
        status_code=status_code,
        error=error,
        next_backoff_seconds=None,
    )


# ---------------------------------------------------------------------------
# Dead-letter persistence
# ---------------------------------------------------------------------------
async def write_dead_letter(
    session: AsyncSession,
    *,
    account_id: int,
    receiver_kind: str,
    receiver_id: int | None,
    url: str,
    event_name: str,
    event_id: str | None,
    body: dict[str, Any],
    outcome: DeliveryOutcome,
    attempts: int,
) -> WebhookDeadLetter:
    row = WebhookDeadLetter(
        account_id=account_id,
        receiver_kind=receiver_kind,
        receiver_id=receiver_id,
        url=url,
        event_name=event_name,
        event_id=event_id,
        body=body,
        last_status_code=outcome.status_code,
        last_error=outcome.error,
        attempts=attempts,
        last_attempted_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(row)
    await session.flush()
    log.warning(
        "webhook.dead_letter receiver_kind=%s receiver_id=%s url=%s "
        "attempts=%s last_status=%s",
        receiver_kind,
        receiver_id,
        url,
        attempts,
        outcome.status_code,
    )
    return row


# ---------------------------------------------------------------------------
# ARQ task wrapper
# ---------------------------------------------------------------------------
async def deliver_webhook_task(
    ctx: dict[str, Any],
    *,
    account_id: int,
    receiver_kind: str,
    receiver_id: int | None,
    url: str,
    event_name: str,
    body: dict[str, Any],
    secret: str | None,
) -> dict[str, Any]:
    """ARQ task body. ``ctx['job_try']`` is the attempt number (1-indexed)."""
    attempt = int(ctx.get("job_try", 1))
    outcome = await deliver_webhook_now(
        url=url, body=body, secret=secret, attempt=attempt
    )

    if outcome.kind == "ok":
        return {
            "url": url,
            "status_code": outcome.status_code,
            "attempts": attempt,
        }

    if outcome.kind == "retry":
        from arq.worker import Retry

        log.warning(
            "webhook.delivery.retry receiver_kind=%s url=%s attempt=%s "
            "status=%s defer=%ss",
            receiver_kind,
            url,
            attempt,
            outcome.status_code,
            outcome.next_backoff_seconds,
        )
        raise Retry(defer=outcome.next_backoff_seconds)

    # Dead-letter: write the row + give up. We open our own session
    # from the cached engine so the task body doesn't depend on the
    # listener's session being alive.
    engine = _engine_from_ctx(ctx)
    sessionmaker = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with sessionmaker() as session:
        await write_dead_letter(
            session,
            account_id=account_id,
            receiver_kind=receiver_kind,
            receiver_id=receiver_id,
            url=url,
            event_name=event_name,
            event_id=str(body.get("event_id")) if body.get("event_id") else None,
            body=body,
            outcome=outcome,
            attempts=attempt,
        )
        await session.commit()

    return {
        "url": url,
        "status_code": outcome.status_code,
        "attempts": attempt,
        "dead_letter": True,
    }


def _engine_from_ctx(ctx: dict[str, Any]) -> AsyncEngine:
    engine = ctx.get("engine")
    if engine is None:
        from app.core.config import get_settings

        engine = create_async_engine(
            get_settings().database_url, pool_pre_ping=True
        )
        ctx["engine"] = engine
    return engine  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Listener-facing entry point
# ---------------------------------------------------------------------------
async def enqueue_delivery(
    *,
    session: AsyncSession,
    account_id: int,
    receiver_kind: str,
    receiver_id: int | None,
    url: str,
    event_name: str,
    body: dict[str, Any],
    secret: str | None,
) -> None:
    """Push the delivery onto the ARQ queue.

    Falls back to a single inline attempt when no ARQ pool is
    reachable. The inline path:
      * Does NOT retry (one shot).
      * On terminal failure (non-2xx or transport error) still writes
        a dead-letter row so the operator gets the same forensic
        signal regardless of whether the worker was up.
    The fallback exists so the dev surface + integration tests that
    don't boot a worker still see end-to-end behaviour.
    """
    if not url:
        return

    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    settings = get_settings()
    try:
        pool = await create_pool(
            RedisSettings.from_dsn(settings.arq_redis_url)
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "webhook.enqueue.no_pool receiver_kind=%s url=%s err=%s — running inline",
            receiver_kind,
            url,
            exc,
        )
        await _run_inline(
            session=session,
            account_id=account_id,
            receiver_kind=receiver_kind,
            receiver_id=receiver_id,
            url=url,
            event_name=event_name,
            body=body,
            secret=secret,
        )
        return
    try:
        await pool.enqueue_job(
            "deliver_webhook_task",
            account_id=account_id,
            receiver_kind=receiver_kind,
            receiver_id=receiver_id,
            url=url,
            event_name=event_name,
            body=body,
            secret=secret,
        )
    finally:
        await pool.aclose()


async def _run_inline(
    *,
    session: AsyncSession,
    account_id: int,
    receiver_kind: str,
    receiver_id: int | None,
    url: str,
    event_name: str,
    body: dict[str, Any],
    secret: str | None,
) -> None:
    """Single-attempt fallback for envs without a worker. Writes a
    dead-letter row on terminal failure so the operator still sees
    misbehaving receivers."""
    outcome = await deliver_webhook_now(
        url=url, body=body, secret=secret, attempt=MAX_ATTEMPTS
    )
    if outcome.kind == "ok":
        return
    # ``retry`` collapses to ``dead_letter`` in the inline path —
    # there's no worker to come back later. We pin the attempt count
    # at 1 in that case so the operator can tell the dead-letter came
    # from the fallback rather than from worker exhaustion.
    attempts = MAX_ATTEMPTS if outcome.kind == "dead_letter" else 1
    await write_dead_letter(
        session,
        account_id=account_id,
        receiver_kind=receiver_kind,
        receiver_id=receiver_id,
        url=url,
        event_name=event_name,
        event_id=str(body.get("event_id")) if body.get("event_id") else None,
        body=body,
        outcome=outcome,
        attempts=attempts,
    )


__all__ = [
    "BACKOFF_SECONDS",
    "HTTP_TIMEOUT_SECONDS",
    "MAX_ATTEMPTS",
    "RECEIVER_KIND_AGENT_BOT",
    "RECEIVER_KIND_WEBHOOK",
    "DeliveryOutcome",
    "build_headers",
    "deliver_webhook_now",
    "deliver_webhook_task",
    "enqueue_delivery",
    "write_dead_letter",
]
