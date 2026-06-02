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

    fastmcp 3.x exposes HTTP headers via :func:`get_http_headers` from
    its dependencies module — that's the supported way to read inbound
    headers. ``include_all=True`` is required because ``authorization``
    is stripped from the default view (fastmcp considers it a
    forwarding-sensitive header). For stdio transport there's no HTTP
    request and the helper returns ``{}``, so we fall back to the
    ``MCP_BEARER_TOKEN`` env var.
    """
    import os

    # HTTP transport — read headers via the supported fastmcp helper
    # (the older ``context.fastmcp_context.request_context.headers`` path
    # disappeared in fastmcp 3.x).
    try:
        from fastmcp.server.dependencies import get_http_headers

        headers = get_http_headers(include_all=True)
    except Exception:  # noqa: BLE001 — never raise from auth path
        headers = {}
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
