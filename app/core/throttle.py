"""A ceiling on failed sign-ins.

The login answers on a public URL, and nothing slowed down someone trying
passwords against it — bcrypt made each guess cost a few milliseconds, not
a lock. This counts *failures* in Redis over a fixed window, on two keys:

* **per account** (``email``) — the brute-force case: one address, many
  passwords. After :data:`EMAIL_LIMIT` failures the address answers 429
  until the window passes, *even with the right password*, so the correct
  guess does not tell the attacker it was correct.
* **per client address** — spraying: one source, many addresses. Looser,
  because an office behind one NAT is many people.

Only failures count, and a success clears the account's counter, so a
person who mistypes twice and then gets it right starts clean.

Two decisions that matter more than the numbers:

* **The address is only believed from our own proxy.** Browsers reach the
  backend through the Next BFF on the same host, so every request arrives
  from ``127.0.0.1``. Keying on that would put every visitor in one bucket
  and let one attacker lock *everyone* out. So the client address comes
  from ``X-Forwarded-For`` when — and only when — the peer is loopback;
  when there is no real address, the per-address limit is skipped rather
  than applied to the whole world. The per-account limit still holds.
* **Fails open.** If Redis is down the login keeps working, with a
  warning in the log. Locking every user out because a cache is
  restarting would be worse than the risk this closes.

The per-account lock can be used to keep a known user out for fifteen
minutes by failing on purpose. That is the usual price of this kind of
limit, and the window is kept short because of it.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass

from redis import asyncio as redis_asyncio
from redis.exceptions import RedisError
from starlette.requests import Request

from app.core.config import get_settings

log = logging.getLogger(__name__)

WINDOW_SECONDS = 15 * 60
EMAIL_LIMIT = 10
IP_LIMIT = 30

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}

# One client per event loop: an asyncio Redis connection belongs to the loop
# that opened it, and reusing it from another (tests run one loop per test)
# raises instead of failing over to the open path.
_clients: dict[int, redis_asyncio.Redis] = {}


def _redis() -> redis_asyncio.Redis:
    loop_id = id(asyncio.get_running_loop())
    client = _clients.get(loop_id)
    if client is None:
        client = _clients[loop_id] = redis_asyncio.from_url(
            get_settings().redis_url,
            decode_responses=True,
            # Short on purpose: this sits in front of every sign-in, and a
            # Redis that does not answer must cost milliseconds, not seconds.
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return client


def client_address(request: Request) -> str | None:
    """The visitor's address, or ``None`` when we cannot know it."""
    peer = request.client.host if request.client else None
    if peer in _LOOPBACK:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        # A proxy that saw no real client forwards its own peer; loopback
        # here is "unknown", not an address to key everybody on.
        if not first or first in _LOOPBACK:
            return None
        return first
    return peer


def _keys(email: str, address: str | None) -> list[tuple[str, int]]:
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()[:32]
    keys = [(f"throttle:login:email:{digest}", EMAIL_LIMIT)]
    if address:
        keys.append((f"throttle:login:ip:{address}", IP_LIMIT))
    return keys


@dataclass(frozen=True, slots=True)
class Verdict:
    allowed: bool
    retry_after: int = 0


async def check(email: str, address: str | None) -> Verdict:
    """Whether a sign-in attempt may proceed at all."""
    try:
        r = _redis()
        for key, limit in _keys(email, address):
            count = await r.get(key)
            if count is not None and int(count) >= limit:
                ttl = await r.ttl(key)
                return Verdict(False, max(int(ttl), 1))
    except (RedisError, OSError) as exc:
        log.warning("throttle.unavailable err=%s", type(exc).__name__)
    return Verdict(True)


async def record_failure(email: str, address: str | None) -> None:
    try:
        r = _redis()
        for key, _limit in _keys(email, address):
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, WINDOW_SECONDS)
    except (RedisError, OSError) as exc:
        log.warning("throttle.unavailable err=%s", type(exc).__name__)


async def record_success(email: str) -> None:
    try:
        await _redis().delete(_keys(email, None)[0][0])
    except (RedisError, OSError) as exc:
        log.warning("throttle.unavailable err=%s", type(exc).__name__)


__all__ = [
    "EMAIL_LIMIT",
    "IP_LIMIT",
    "WINDOW_SECONDS",
    "Verdict",
    "check",
    "client_address",
    "record_failure",
    "record_success",
]
