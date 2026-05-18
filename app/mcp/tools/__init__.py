"""Tool registration hub.

Each submodule defines tools as ``async def`` functions and exposes a
``register(mcp)`` callback that the server's :func:`build_server`
calls. Keeping registration explicit (rather than module-import side
effects) makes the surface auditable from one place.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register_all(mcp: FastMCP) -> None:
    """Register every tool module on the server."""
    from app.mcp.tools.conversations import register as register_conversations
    from app.mcp.tools.health import register as register_health

    register_health(mcp)
    register_conversations(mcp)


__all__ = ["register_all"]
