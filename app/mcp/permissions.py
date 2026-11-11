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

from app.core.errors import ChatwootHTTPException
from app.mcp.context import current_mcp_context
from app.mcp.models import scope_satisfies

Scope = Literal["read", "write", "admin"]


class MCPPermissionError(Exception):
    """Raised when a tool is called with insufficient scope."""


def as_value_error(exc: ChatwootHTTPException) -> ValueError:
    """The service's message as a tool error (``errors`` appended)."""
    detail = exc.detail
    if not isinstance(detail, dict):
        return ValueError(str(detail))
    msg = detail.get("message") or detail.get("error") or str(detail)
    errors = detail.get("errors")
    if isinstance(errors, list) and errors:
        msg = f"{msg}: {'; '.join(str(e) for e in errors)}"
    return ValueError(str(msg))


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
            try:
                return await fn(*args, **kwargs)
            except ChatwootHTTPException as exc:
                # The services speak HTTP (422 + {"message": ...}); an MCP
                # client needs the message itself, not "422: {...}".
                raise as_value_error(exc) from exc

        return wrapper

    return decorator


__all__ = ["MCPPermissionError", "Scope", "as_value_error", "requires"]
