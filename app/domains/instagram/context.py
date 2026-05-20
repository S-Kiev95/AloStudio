"""Session helper for the Instagram publishing worker.

The ARQ task body + the inline fallback both need a fresh
``AsyncSession`` committed on success / rolled back on failure. We
open a per-call engine with NullPool — same rationale as the MCP
layer: asyncpg connections bind to the event loop they're created on,
and the worker's loop differs from the request loop, so a cached
pooled engine would hand out dead connections.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings


@asynccontextmanager
async def open_publish_session():
    """Yield a fresh AsyncSession; commit on clean exit, rollback on
    exception."""
    engine = create_async_engine(
        get_settings().database_url, poolclass=NullPool
    )
    try:
        sessionmaker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()


__all__ = ["open_publish_session"]
