"""CLI entry point for the AloStudio MCP server.

Two transports:

  * ``python -m app.mcp stdio``                       — Claude Desktop / local agent dev.
  * ``python -m app.mcp http --host 0.0.0.0 --port 8765`` — remote agents over streamable HTTP.

Both use the same :func:`app.mcp.server.build_server` instance, so the
auth middleware + tool surface are identical across transports.

Auth: agents pass ``Authorization: Bearer <mcp_token>``. For stdio
where there's no HTTP header, the ``MCP_BEARER_TOKEN`` env var is the
fallback the auth middleware reads.

Run-time considerations:
  * HTTP transport binds the asyncio event loop FastMCP creates
    internally — we don't need an external uvicorn invocation. Pair
    with a TLS terminator (nginx / Caddy) in production.
  * The default port (8765) is documented in the README + the
    integration doc so external receivers know where to point.
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.mcp.server import build_server


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.mcp",
        description="Launch the AloStudio MCP server (stdio or HTTP transport).",
    )
    sub = parser.add_subparsers(dest="transport", required=True)

    sub.add_parser("stdio", help="Run over stdio (default for local agents).")

    http = sub.add_parser("http", help="Run streamable HTTP transport.")
    http.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1; use 0.0.0.0 to expose).",
    )
    http.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Bind port (default: 8765).",
    )
    http.add_argument(
        "--path",
        default="/mcp",
        help="HTTP path the server listens on (default: /mcp).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    args = _build_parser().parse_args(argv)
    server = build_server()

    if args.transport == "stdio":
        server.run(transport="stdio")
        return 0

    if args.transport == "http":
        # ``streamable-http`` is fastmcp's modern HTTP transport — it
        # supports both unary tool calls and streaming responses, which
        # the older ``http`` shim doesn't. We pin to it so remote agents
        # always get the richer surface.
        server.run(
            transport="http",
            host=args.host,
            port=args.port,
            path=args.path,
        )
        return 0

    # argparse's ``required=True`` should make this unreachable.
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
