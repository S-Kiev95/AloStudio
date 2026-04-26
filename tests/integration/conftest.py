"""Integration fixtures: DB session wired to the alostudio_test database.

Each test function runs inside a nested transaction that is rolled back at
teardown, so tests never leave residual rows — identical in spirit to
Rails' ``use_transactional_fixtures``.

Why an engine per test:
  On Windows, ``asyncpg`` uses ``ProactorEventLoop`` sockets that are tied
  to the event loop that created them. ``pytest-asyncio`` in function-scoped
  mode creates a fresh loop per test, which makes a process-wide cached
  engine (``app.core.db.get_engine()``) hand out connections bound to dead
  loops on the second test. Using a per-test engine with ``NullPool`` keeps
  every connection local to the test's own loop and disposes cleanly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings


@pytest.fixture(autouse=True)
async def _reset_broadcaster_per_test() -> AsyncIterator[None]:
    """Tear down the realtime broadcaster between tests.

    The :class:`RealtimeBroadcaster` lazily binds a ``redis.asyncio.Redis``
    client to the event loop active at first publish. ``pytest-asyncio``
    creates a fresh loop per test, so without this teardown the next
    test would inherit a Redis client whose underlying writer references
    the dead loop and crashes with ``RuntimeError: Event loop is closed``.

    The lifespan version of this lives in :func:`app.main.lifespan` and
    runs only when tests use ``alo_app`` / ``LifespanManager``. The 4a
    integration suite imports the singleton ``app`` directly and never
    fires lifespan, hence the explicit reset here.
    """
    yield
    from app.core.realtime import reset_broadcaster

    await reset_broadcaster()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Per-test AsyncSession with auto-rollback.

    Opens a short-lived engine + connection, begins an outer transaction
    we never commit, and yields a SQLModel AsyncSession bound to that
    connection. Anything the test writes is visible to queries in the same
    session (the builder runs inside a SAVEPOINT) but vanishes on rollback.
    """
    engine = create_async_engine(
        get_settings().database_url,
        poolclass=NullPool,
        echo=False,
    )
    try:
        async with engine.connect() as connection:
            trans = await connection.begin()
            session_maker = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                join_transaction_mode="create_savepoint",
            )
            async with session_maker() as session:
                try:
                    yield session
                finally:
                    await session.close()
            if trans.is_active:
                await trans.rollback()
    finally:
        await engine.dispose()
