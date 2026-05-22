"""FastMCP server — entry point for AI agents.

The actual tools live in submodules (``tools/conversations.py`` etc.).
This module wires the FastMCP instance + the auth middleware + the
session-binding lifespan.

Two transports supported out of the box:

  * **stdio** — for Claude Desktop / local agent dev.
    ``python -m app.mcp stdio``
  * **HTTP**  — for remote agents.
    ``python -m app.mcp http --host 0.0.0.0 --port 8765``

Auth: agents pass ``Authorization: Bearer <mcp_token>``. The token
must exist in ``mcp_tokens`` and resolve to a live Account. The
resolved :class:`MCPContext` is bound onto the contextvar
(:func:`bind_mcp_context`) so each tool body reads it via
:func:`current_mcp_context` without polluting its signature.

For tests, instantiate the FastMCP server in-process and use the
``Client(mcp)`` shortcut — the in-memory transport bypasses HTTP
entirely. Tests inject a context via :func:`bind_test_context`.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.mcp.context import (
    MCPContext,
    bind_mcp_context,
    open_mcp_session,
    reset_mcp_context,
)
from app.mcp.service import MCPAuthError, resolve_token

log = logging.getLogger(__name__)

INSTRUCTIONS = """\
AloStudio MCP server. Tools cover conversation operations on a
Chatwoot-compatible backend: list / show / resolve / assign /
reply / label / tag / route to humans.

Pass ``Authorization: Bearer <mcp_token>`` on every connection.
Each token is scoped to one account and a permission level
(read / write / admin).
"""


# ---------------------------------------------------------------------------
# Auth middleware — binds MCPContext to the contextvar for each call.
# ---------------------------------------------------------------------------
class AuthMiddleware(Middleware):
    """Resolve the bearer token + bind the context.

    For ``tools/call`` and ``tools/list`` we open a session and resolve
    the token. Other method types (initialize, ping) skip auth so the
    handshake works before the client knows it needs to authenticate.
    """

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next
    ):
        async with open_mcp_session() as session:
            token = _extract_token(context)
            ctx = await resolve_token(session, token_value=token)
            ctx.session = session
            cv_token = bind_mcp_context(ctx)
            try:
                return await call_next(context)
            finally:
                reset_mcp_context(cv_token)

    async def on_list_tools(
        self, context: MiddlewareContext[Any], call_next
    ):
        # Listing tools is also auth-gated so unauthenticated clients
        # can't discover the surface.
        async with open_mcp_session() as session:
            token = _extract_token(context)
            ctx = await resolve_token(session, token_value=token)
            ctx.session = session
            cv_token = bind_mcp_context(ctx)
            try:
                return await call_next(context)
            finally:
                reset_mcp_context(cv_token)


def _extract_token(context: MiddlewareContext[Any]) -> str:
    """Pull the Bearer token from the MCP request context.

    fastmcp 3.x stores HTTP headers on ``context.fastmcp_context`` or
    falls through to env vars for stdio. The ``MCP_BEARER_TOKEN`` env
    var override is useful for stdio transport where there's no
    header to read.
    """
    import os

    # HTTP transport — headers via fastmcp_context.
    fc = getattr(context, "fastmcp_context", None)
    if fc is not None:
        request = getattr(fc, "request_context", None)
        if request is not None:
            headers = getattr(request, "headers", None) or {}
            auth = headers.get("authorization") or headers.get("Authorization")
            if auth and auth.lower().startswith("bearer "):
                return auth[7:].strip()

    # stdio fallback — env var.
    env_token = os.environ.get("MCP_BEARER_TOKEN")
    if env_token:
        return env_token

    raise MCPAuthError("missing bearer token")


# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------
def build_server() -> FastMCP:
    """Build the FastMCP instance with auth middleware + tool
    registrations. Called by the entry point + by tests."""
    mcp = FastMCP(
        name="AloStudio",
        instructions=INSTRUCTIONS,
        middleware=[AuthMiddleware()],
    )
    # Register tool modules (each calls ``mcp.add_tool(...)`` for its
    # tools so the order + grouping stays explicit at the module level).
    from app.mcp.tools import register_all

    register_all(mcp)
    return mcp


__all__ = ["AuthMiddleware", "INSTRUCTIONS", "build_server"]
