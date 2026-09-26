"""A ceiling on failed sign-ins.

The login answers on a public URL and nothing slowed down someone trying
passwords. These pin the behaviours that matter, not just "429 appears":
the right password is refused once an account is over the limit, a
success wipes the slate, one source cannot spray many accounts — and the
limit never keys on the proxy's own address, which would let one attacker
lock *everyone* out.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from redis import asyncio as redis_asyncio

from app.core import throttle
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.main import app

pytestmark = pytest.mark.integration

PASSWORD = "Password123!"
TEST_REDIS = "redis://127.0.0.1:6380/15"


@pytest.fixture(autouse=True)
async def clean_counters(monkeypatch):
    """Counters live in Redis for fifteen minutes; without this a re-run
    would start locked.

    Also points Redis at ``127.0.0.1`` for this module only. The suite's
    default is ``localhost``, which on Windows tries ::1 first and stalls;
    the throttle's half-second timeout never gets past it, fails open, and
    every test here would pass with the limit never running — two did,
    before this. It is not changed suite-wide because other tests quietly
    *depend* on Redis being unreachable (see PLAN.pendientes.md).
    """
    monkeypatch.setenv("REDIS_URL", TEST_REDIS)
    get_settings.cache_clear()
    monkeypatch.setattr(throttle, "_clients", {})

    async def wipe() -> None:
        # The constant, not the settings: the Redis-down test points the
        # settings at a dead port, and teardown runs before that is undone.
        r = redis_asyncio.from_url(TEST_REDIS)
        try:
            keys = [k async for k in r.scan_iter("throttle:login:*")]
            if keys:
                await r.delete(*keys)
        finally:
            await r.aclose()

    await wipe()
    yield
    await wipe()
    get_settings.cache_clear()


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)  # peer is 127.0.0.1, like the BFF
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
async def user(db_session):
    return (
        await AccountBuilder(
            db_session,
            AccountBuilderParams(
                email="victima@throttle.example.com",
                account_name="Throttle",
                user_full_name="Víctima",
                user_password=PASSWORD,
                confirmed=True,
            ),
        ).perform()
    ).user


async def _sign_in(client, email, password, xff=None):
    headers = {"X-Forwarded-For": xff} if xff else {}
    return await client.post(
        "/auth/sign_in", json={"email": email, "password": password}, headers=headers
    )


async def test_over_the_limit_even_the_right_password_is_refused(client, user):
    for _ in range(throttle.EMAIL_LIMIT):
        assert (await _sign_in(client, user.email, "adivinanza")).status_code == 401

    resp = await _sign_in(client, user.email, PASSWORD)

    # Answering 200 here would tell the attacker their last guess was right.
    assert resp.status_code == 429
    assert resp.json()["code"] == "too_many_attempts"
    assert int(resp.headers["retry-after"]) > 0


async def test_a_success_starts_the_count_again(client, user):
    """Guards against over-locking, not the lock itself — it passes with
    the limit removed entirely, which is checked and expected. What it
    catches is a limit that forgets to reset and punishes a person who
    mistyped a few times and then got in."""
    for _ in range(throttle.EMAIL_LIMIT - 1):
        await _sign_in(client, user.email, "adivinanza")
    assert (await _sign_in(client, user.email, PASSWORD)).status_code == 200

    for _ in range(throttle.EMAIL_LIMIT - 1):
        assert (await _sign_in(client, user.email, "adivinanza")).status_code == 401
    assert (await _sign_in(client, user.email, PASSWORD)).status_code == 200


async def test_one_source_cannot_spray_many_accounts(client, monkeypatch):
    monkeypatch.setattr(throttle, "IP_LIMIT", 3)
    for i in range(3):
        await _sign_in(client, f"nadie{i}@x.example.com", "x", xff="203.0.113.7")

    resp = await _sign_in(client, "otro@x.example.com", "x", xff="203.0.113.7")
    assert resp.status_code == 429

    # A different visitor is untouched.
    resp = await _sign_in(client, "otro@x.example.com", "x", xff="198.51.100.9")
    assert resp.status_code == 401


@pytest.mark.parametrize("xff", [None, "127.0.0.1", "127.0.0.1, 10.0.0.1"])
async def test_the_proxy_address_is_never_a_bucket(client, monkeypatch, xff):
    """Every browser request reaches the backend from the BFF on 127.0.0.1.

    Keying on that would put the whole world in one bucket, and one
    attacker could lock everybody out. With no real client address the
    per-address limit is skipped; the per-account one still holds.
    """
    monkeypatch.setattr(throttle, "IP_LIMIT", 3)
    for i in range(6):
        resp = await _sign_in(client, f"n{i}@y.example.com", "x", xff=xff)
        assert resp.status_code == 401, f"intento {i} con xff={xff!r}"


async def test_with_redis_down_the_login_still_works(client, user, monkeypatch):
    """Locking every user out because a cache restarted would be worse than
    the risk this closes."""
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()
    monkeypatch.setattr(throttle, "_clients", {})
    try:
        resp = await _sign_in(client, user.email, PASSWORD)
    finally:
        get_settings.cache_clear()
    assert resp.status_code == 200
