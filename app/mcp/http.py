"""The MCP server over HTTP, served by the backend itself at ``/mcp``.

Remote clients call it with ``Authorization: Bearer <token>``: an "API y
MCP" token or an OAuth access token. A request without a usable token gets
a 401 whose ``WWW-Authenticate`` points to the protected-resource metadata
(RFC 9728): that is how an OAuth-capable client (Claude or ChatGPT
connectors) finds out where to send the user to authorize it.

The FastMCP :class:`AuthMiddleware` still resolves the token on every tool
call; the gate here only answers at the HTTP level, which the MCP layer
cannot do.
"""

from __future__ import annotations

from fastmcp.server.http import StarletteWithLifespan
from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.domains.oauth.service import protected_resource_metadata_url
from app.mcp.context import open_mcp_session
from app.mcp.server import build_server
from app.mcp.service import MCPAuthError, resolve_token

MCP_PATH = "/mcp"


class BearerGate:
    """401 for HTTP requests without a token the MCP layer would accept."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # CORS preflights carry no credentials by design.
        if scope["type"] == "http" and scope.get("method") != "OPTIONS":
            if not await _has_valid_token(scope):
                response = JSONResponse(
                    {"error": "invalid_token", "error_description": "Falta un token válido."},
                    status_code=401,
                    headers={
                        "WWW-Authenticate": (
                            f'Bearer resource_metadata="{protected_resource_metadata_url()}"'
                        )
                    },
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


async def _has_valid_token(scope: Scope) -> bool:
    auth = Headers(scope=scope).get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return False
    try:
        async with open_mcp_session() as session:
            await resolve_token(session, token_value=auth[7:].strip())
    except MCPAuthError:
        return False
    return True


def build_http_app() -> StarletteWithLifespan:
    """The MCP server as an ASGI app answering at ``/mcp``. Stateless: each
    request stands alone, so any backend worker can serve it."""
    return build_server().http_app(
        path=MCP_PATH,
        middleware=[Middleware(BearerGate)],
        stateless_http=True,
    )


__all__ = ["MCP_PATH", "BearerGate", "build_http_app"]
