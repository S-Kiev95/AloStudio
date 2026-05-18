"""MCPToken — API token used by AI agents to invoke MCP tools.

Separate from the polymorphic ``access_tokens`` table because:

  * MCP tokens are **account-scoped** (an agent acts as an account,
    not a user). access_tokens are owner-scoped (User / AgentBot).
  * MCP tokens carry a permission ``scope`` (read / write / admin)
    that the tool dispatch consults; access_tokens have no scope —
    they grant full dashboard-equivalent power.
  * The lifecycle is independent — rotating an MCP token doesn't
    affect dashboard sessions and vice versa.

The ``user_id`` column is optional and informational only — it lets
the dashboard's "Who created this token?" view render a name without
giving the token user-level identity at runtime.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

MCPScope = Literal["read", "write", "admin"]

# Scope hierarchy: a higher scope subsumes lower ones.
_SCOPE_LEVEL: dict[str, int] = {"read": 0, "write": 1, "admin": 2}


def scope_satisfies(token_scope: str, required: str) -> bool:
    """Mirror ``Pundit``-style permission checks: a write token can
    call read tools, an admin token can call write tools."""
    if token_scope not in _SCOPE_LEVEL or required not in _SCOPE_LEVEL:
        return False
    return _SCOPE_LEVEL[token_scope] >= _SCOPE_LEVEL[required]


class MCPToken(TimestampMixin, table=True):
    __tablename__ = "mcp_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="index_mcp_tokens_on_token"),
        Index("index_mcp_tokens_on_account_id", "account_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    token: str = Field(sa_column=Column(String, nullable=False))
    scope: str = Field(
        default="read",
        sa_column=Column(String, nullable=False, server_default="read"),
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


__all__ = [
    "MCPScope",
    "MCPToken",
    "scope_satisfies",
]
