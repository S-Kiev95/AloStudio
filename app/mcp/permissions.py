"""Permission helpers for MCP tools.

Each tool declares its required scope (read / write / admin) via the
:func:`requires` decorator. The decorator wraps the tool body so the
scope check runs before the body — same model as Rails' Pundit
``authorize`` before_action.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from app.mcp.context import current_mcp_context
from app.mcp.models import scope_satisfies

Scope = Literal["read", "write", "admin"]


class MCPPermissionError(Exception):
    """Raised when a tool is called with insufficient scope."""


def requires(scope: Scope):
    """Decorator factory — wrap a tool body to enforce ``scope``."""

    def decorator(
        fn: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = current_mcp_context()
            if not scope_satisfies(ctx.scope, scope):
                raise MCPPermissionError(
                    f"tool requires {scope!r} scope; token has {ctx.scope!r}"
                )
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


__all__ = ["MCPPermissionError", "Scope", "requires"]
