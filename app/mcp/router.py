"""MCP token admin HTTP endpoints.

The MCP server itself authenticates AI agents via Bearer tokens (see
:mod:`app.mcp.service.resolve_token`). This router is the *dashboard*
side — it lets account admins manage those tokens.

Route map (admin-only on every path):

  * ``GET    /api/v1/accounts/{id}/mcp_tokens``
  * ``POST   /api/v1/accounts/{id}/mcp_tokens``           → secret in body
  * ``PATCH  /api/v1/accounts/{id}/mcp_tokens/{tid}``     → rename / re-scope
  * ``POST   /api/v1/accounts/{id}/mcp_tokens/{tid}/rotate`` → secret in body
  * ``DELETE /api/v1/accounts/{id}/mcp_tokens/{tid}``     → head :ok

Wire shape:

  * ``index``  → ``{"payload": [<token-no-secret>, ...]}``
  * ``create`` → bare ``<token-with-secret>`` (secret visible once)
  * ``rotate`` → bare ``<token-with-secret>``
  * ``update`` → bare ``<token-no-secret>``
  * ``destroy`` → ``{}`` (200, empty body)
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.mcp.models import MCPToken
from app.mcp.presenters import present_token, present_token_with_secret
from app.mcp.schemas import MCPTokenCreate, MCPTokenUpdate
from app.mcp.service import (
    create_token,
    list_tokens,
    revoke_token,
    rotate_token,
    update_token,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/mcp_tokens",
    tags=["mcp-tokens"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _find(
    session: AsyncSession, *, account_id: int, token_id: int
) -> MCPToken:
    row = (
        await session.exec(
            select(MCPToken).where(
                MCPToken.id == token_id,
                MCPToken.account_id == account_id,
            )
        )
    ).first()
    if row is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("")
async def index_tokens(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    rows = await list_tokens(session, account_id=ctx.account.id)
    return {"payload": [present_token(r) for r in rows]}


@router.post("", status_code=status.HTTP_200_OK)
async def create_token_endpoint(
    payload: MCPTokenCreate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mint a fresh token. The plain-text ``token`` value is included in
    the response body — this is the only time it's reachable."""
    assert ctx.account.id is not None and ctx.user.id is not None
    row = await create_token(
        session,
        account_id=ctx.account.id,
        name=payload.name,
        scope=payload.scope,
        user_id=ctx.user.id,
    )
    return present_token_with_secret(row)


@router.patch("/{token_id}")
async def update_token_endpoint(
    token_id: Annotated[int, Path()],
    payload: MCPTokenUpdate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Rename or re-scope an existing token. The secret is **not** rotated
    — use ``POST /rotate`` for that. Response omits the secret."""
    assert ctx.account.id is not None
    row = await _find(
        session, account_id=ctx.account.id, token_id=token_id
    )
    updated = await update_token(
        session,
        token=row,
        name=payload.name,
        scope=payload.scope,
    )
    return present_token(updated)


@router.post("/{token_id}/rotate", status_code=status.HTTP_200_OK)
async def rotate_token_endpoint(
    token_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mint a new secret in place. Returns the rotated row WITH the new
    secret in the body — clients still using the old one will start
    failing 401 immediately."""
    assert ctx.account.id is not None
    row = await _find(
        session, account_id=ctx.account.id, token_id=token_id
    )
    rotated = await rotate_token(session, token=row)
    return present_token_with_secret(rotated)


@router.delete("/{token_id}", status_code=status.HTTP_200_OK)
async def destroy_token_endpoint(
    token_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Revoke (hard-delete) a token. Empty 200 body — Chatwoot-style."""
    assert ctx.account.id is not None
    row = await _find(
        session, account_id=ctx.account.id, token_id=token_id
    )
    await revoke_token(session, token=row)
    return {}


__all__ = ["router"]
