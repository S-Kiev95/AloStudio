"""Container status polling.

``GET /{container-id}?fields=status_code`` — drives a container from
``IN_PROGRESS`` to a terminal state. Meta's published guidance is to
**poll once per minute for no more than 5 minutes**; we honour that
exactly via the cadence constants.

The poller is split into two layers:

  * :func:`fetch_status` — one HTTP call, returns the current
    ``status_code`` (or an error sentinel). Pure + mockable.
  * :func:`poll_until_terminal` — the loop with sleeps. The ARQ task
    uses this; tests inject a tiny ``sleep_fn`` so they don't
    actually wait 5 minutes.

Image containers usually return ``FINISHED`` on the first poll;
video/reels/stories take longer (the loop matters there — I.3+).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.domains.inboxes.models import InstagramChannel

log = logging.getLogger(__name__)

# Meta's published cadence: once per minute, max 5 minutes.
POLL_INTERVAL_SECONDS = 60
POLL_MAX_ATTEMPTS = 5

# Terminal status codes — the loop stops when it sees one of these.
_TERMINAL = {"FINISHED", "ERROR", "EXPIRED", "PUBLISHED"}


@dataclass(slots=True)
class StatusResult:
    """One poll's outcome.

    ``status_code`` is Meta's value when the call succeeded; ``None``
    + ``error`` set when the HTTP call itself failed (which we treat
    as a soft failure — keep polling until attempts run out)."""

    status_code: str | None
    error: str | None = None


def _status_url(container_id: str) -> str:
    # Host is task-local (Facebook vs Instagram Login) — see graph.py.
    from app.domains.instagram.graph import graph_base

    return f"{graph_base()}/{container_id}"


async def fetch_status(
    channel: InstagramChannel, *, container_id: str
) -> StatusResult:
    """One ``GET /{container}?fields=status_code`` call.

    Never raises — transport / API errors come back as
    ``StatusResult(status_code=None, error=...)`` so the loop can
    decide whether to retry or give up."""
    if not channel.access_token:
        return StatusResult(status_code=None, error="missing_access_token")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _status_url(container_id),
                params={
                    "fields": "status_code",
                    "access_token": channel.access_token,
                },
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return StatusResult(status_code=None, error=str(exc)[:300])
    if resp.status_code >= 400:
        return StatusResult(
            status_code=None,
            error=f"http_{resp.status_code}:{resp.text[:200]}",
        )
    try:
        payload = resp.json()
    except ValueError:
        return StatusResult(status_code=None, error="bad_json")
    code = (
        payload.get("status_code") if isinstance(payload, dict) else None
    )
    if not code:
        return StatusResult(status_code=None, error="no_status_code")
    return StatusResult(status_code=str(code))


async def poll_until_terminal(
    channel: InstagramChannel,
    *,
    container_id: str,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    interval_seconds: int = POLL_INTERVAL_SECONDS,
    max_attempts: int = POLL_MAX_ATTEMPTS,
) -> StatusResult:
    """Poll the container until it reaches a terminal status_code or
    the attempt budget runs out.

    Returns:
      * ``StatusResult("FINISHED")`` — ready to publish
      * ``StatusResult("ERROR" | "EXPIRED")`` — terminal failure
      * ``StatusResult(None, error="timeout")`` — still IN_PROGRESS
        after ``max_attempts`` (Meta's 5-minute ceiling)

    ``sleep_fn`` is injectable so tests run instantly. The first poll
    happens immediately (no leading sleep) since image containers
    are usually FINISHED right away.
    """
    last: StatusResult = StatusResult(status_code=None, error="not_polled")
    for attempt in range(1, max_attempts + 1):
        last = await fetch_status(channel, container_id=container_id)
        if last.status_code in _TERMINAL:
            log.info(
                "instagram.poll.terminal container_id=%s status=%s attempt=%s",
                container_id,
                last.status_code,
                attempt,
            )
            return last
        # IN_PROGRESS or a soft HTTP error — wait + retry (unless this
        # was the last attempt).
        if attempt < max_attempts:
            await sleep_fn(interval_seconds)
    # Budget exhausted without a terminal status.
    log.warning(
        "instagram.poll.timeout container_id=%s last=%s",
        container_id,
        last.status_code or last.error,
    )
    return StatusResult(status_code=None, error="timeout")


__all__ = [
    "POLL_INTERVAL_SECONDS",
    "POLL_MAX_ATTEMPTS",
    "StatusResult",
    "fetch_status",
    "poll_until_terminal",
]
