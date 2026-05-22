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
    from app.mcp.tools.contacts import register as register_contacts
    from app.mcp.tools.conversations import register as register_conversations
    from app.mcp.tools.health import register as register_health
    from app.mcp.tools.instagram import register as register_instagram
    from app.mcp.tools.messages import register as register_messages
    from app.mcp.tools.meta import register as register_meta

    register_health(mcp)
    register_conversations(mcp)
    register_messages(mcp)
    register_contacts(mcp)
    register_meta(mcp)
    register_instagram(mcp)


__all__ = ["register_all"]
