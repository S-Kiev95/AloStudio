"""Pydantic schemas for the MCP token admin CRUD surface.

The MCP server itself authenticates via Bearer tokens (see :mod:`app.mcp.service`).
This module owns the dashboard-side wire schema admins use to manage those
tokens — create / rename / rotate / revoke.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MCPScopeLiteral = Literal["read", "write", "admin"]


class MCPTokenCreate(BaseModel):
    """Body for ``POST /mcp_tokens``."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=255)
    scope: MCPScopeLiteral = "read"


class MCPTokenUpdate(BaseModel):
    """Body for ``PATCH /mcp_tokens/{id}`` — both fields optional."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    scope: MCPScopeLiteral | None = None


__all__ = ["MCPScopeLiteral", "MCPTokenCreate", "MCPTokenUpdate"]
