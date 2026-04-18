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
