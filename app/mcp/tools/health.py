"""Health / introspection tools — useful for agents to verify the
wire is alive before issuing real operations.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from app.mcp.context import current_mcp_context


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="whoami")
    async def whoami() -> dict[str, Any]:
        """Return the resolved account + scope for the current token.

        Agents typically call this once at startup to confirm they're
        authenticated and to learn which account they're acting on
        behalf of.
        """
        ctx = current_mcp_context()
        return {
            "account_id": ctx.account.id,
            "account_name": ctx.account.name,
            "scope": ctx.scope,
            "user": {
                "id": ctx.user.id,
                "name": ctx.user.name,
            },
        }


__all__ = ["register"]
