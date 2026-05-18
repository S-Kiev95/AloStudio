"""Per-call MCP context.

Each MCP tool invocation runs within a request-scoped context built by
:class:`AuthMiddleware`. The context carries:

  * The authenticated :class:`User` (the token's owner).
  * The :class:`Account` in scope (derived from the token's account
    binding for ``mcp_tokens`` rows; defaults to the user's primary
    account for legacy ``access_tokens``).
  * The permission scope (``read`` / ``write`` / ``admin``).
  * An ``AsyncSession`` bound to a fresh DB connection so the tool
    body works inside the listener-driven transaction patterns that
    the rest of the backend uses.

Tools read the context via :func:`current_mcp_context` (a ContextVar
shim). This sidesteps fastmcp's per-call kwargs propagation so each
tool stays a plain ``async def fn(...)`` instead of having to declare
a ``ctx: Context`` parameter.
"""

from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.accounts.models import Account
from app.domains.users.models import User

Scope = Literal["read", "write", "admin"]


@dataclass(slots=True)
class MCPContext:
    """The handful of fields each MCP tool needs.

    Tools never construct one directly — :class:`AuthMiddleware`
    builds it and binds it onto :data:`_ctx_var` for the duration of
    the call."""

    user: User
    account: Account
    scope: Scope
    session: AsyncSession


_ctx_var: contextvars.ContextVar[MCPContext | None] = contextvars.ContextVar(
    "mcp_context", default=None
)


def current_mcp_context() -> MCPContext:
    """Return the binding set by the auth middleware. Raises when
    called outside a tool body (defensive — shouldn't happen)."""
    ctx = _ctx_var.get()
    if ctx is None:
        raise RuntimeError(
            "MCP context not bound — tool body called outside the "
            "auth middleware"
        )
    return ctx


def bind_mcp_context(ctx: MCPContext) -> contextvars.Token:
    """Push ``ctx`` onto the contextvar; returns the reset token."""
    return _ctx_var.set(ctx)


def reset_mcp_context(token: contextvars.Token) -> None:
    _ctx_var.reset(token)


# ---------------------------------------------------------------------------
# Session helper — owned by the MCP layer because the tool body's
# transaction lifecycle is per-call (each tool invocation = one DB
# transaction we commit on success or rollback on failure).
#
# We deliberately open a fresh engine per call (NullPool) rather than
# caching a singleton. Two reasons:
#   1. asyncpg connections bind to the event loop they're created on;
#      test loops change per-test which breaks pooled connections.
#   2. MCP tool calls are low-volume vs the FastAPI request path —
#      paying the connect cost per call is acceptable for the
#      simplicity win.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def open_mcp_session():
    """Context manager yielding a fresh AsyncSession committed on
    successful exit, rolled back on exception."""
    engine = create_async_engine(
        get_settings().database_url,
        poolclass=NullPool,
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


__all__ = [
    "MCPContext",
    "Scope",
    "bind_mcp_context",
    "current_mcp_context",
    "open_mcp_session",
    "reset_mcp_context",
]
