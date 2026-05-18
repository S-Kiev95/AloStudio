"""Token management + auth resolution for the MCP layer.

Owns:
  * Token minting (returns a fresh 32-char URL-safe random) and
    rotation.
  * Auth resolution: takes a Bearer token, returns the bound
    :class:`MCPContext` or raises.
  * ``last_used_at`` bookkeeping on each successful resolve.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.accounts.models import Account
from app.domains.users.models import User
from app.mcp.context import MCPContext
from app.mcp.models import MCPToken


class MCPAuthError(Exception):
    """Raised when a token doesn't resolve to a valid context."""


def mint_token() -> str:
    """Generate a 43-char URL-safe random token (32 bytes encoded)."""
    return secrets.token_urlsafe(32)


async def create_token(
    session: AsyncSession,
    *,
    account_id: int,
    name: str,
    scope: str = "read",
    user_id: int | None = None,
) -> MCPToken:
    """Mint and persist a new MCP token bound to ``account_id``."""
    if scope not in {"read", "write", "admin"}:
        raise ValueError(f"invalid scope: {scope!r}")
    row = MCPToken(
        account_id=account_id,
        user_id=user_id,
        name=name,
        token=mint_token(),
        scope=scope,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def list_tokens(
    session: AsyncSession, *, account_id: int
) -> list[MCPToken]:
    return list(
        (
            await session.exec(
                select(MCPToken)
                .where(MCPToken.account_id == account_id)
                .order_by(MCPToken.id.asc())  # type: ignore[attr-defined]
            )
        ).all()
    )


async def revoke_token(
    session: AsyncSession, *, token: MCPToken
) -> None:
    await session.delete(token)
    await session.flush()


async def resolve_token(
    session: AsyncSession, *, token_value: str
) -> MCPContext:
    """Look up the Bearer token, resolve to a context, stamp
    ``last_used_at``.

    Raises :class:`MCPAuthError` for any failure (unknown token, bound
    account/user missing, etc.) so the middleware can return a single
    canonical 401-style response.
    """
    if not token_value or len(token_value) > 512:
        raise MCPAuthError("malformed token")

    row = (
        await session.exec(
            select(MCPToken).where(MCPToken.token == token_value)
        )
    ).first()
    if row is None:
        raise MCPAuthError("unknown token")

    account = await session.get(Account, row.account_id)
    if account is None:
        raise MCPAuthError("account no longer exists")

    # ``user_id`` is optional on the token — we don't fail when the
    # column is null, but we do try to resolve the user for context
    # binding so logs / audits get a name to display.
    user: User | None = None
    if row.user_id is not None:
        user = await session.get(User, row.user_id)
    if user is None:
        # Synthesise a placeholder User-less context. The downstream
        # tools that genuinely need a user (e.g. assign_agent "self")
        # check for None and 422 out — agents typically operate without
        # a personal identity, so this is the common case.
        user = User(
            id=None,
            name=f"mcp:{row.name}",
            email=f"mcp+{row.id}@machine.invalid",
        )

    row.last_used_at = datetime.now(UTC)
    session.add(row)
    await session.flush()

    return MCPContext(
        user=user,
        account=account,
        scope=row.scope,  # type: ignore[arg-type]
        session=session,
    )


__all__ = [
    "MCPAuthError",
    "create_token",
    "list_tokens",
    "mint_token",
    "resolve_token",
    "revoke_token",
]
