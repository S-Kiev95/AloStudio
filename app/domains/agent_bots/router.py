"""AgentBot HTTP endpoints.

Ports ``Api::V1::Accounts::AgentBotsController`` + the inbox-side
``set_agent_bot`` action.

Route map:

  * ``GET    /api/v1/accounts/{id}/agent_bots``           — admin OR agent
  * ``POST   /api/v1/accounts/{id}/agent_bots``           — admin only
  * ``GET    /api/v1/accounts/{id}/agent_bots/{id}``      — admin OR agent
  * ``PATCH  /api/v1/accounts/{id}/agent_bots/{id}``      — admin only
  * ``DELETE /api/v1/accounts/{id}/agent_bots/{id}``      — admin only
                                                            (head :ok)
  * ``POST   /api/v1/accounts/{id}/agent_bots/{id}/reset_secret``
                                                            — admin only

Inbox-side attach/detach (Chatwoot's ``inboxes#set_agent_bot`` member):

  * ``POST   /api/v1/accounts/{id}/inboxes/{iid}/set_agent_bot``
  * ``DELETE /api/v1/accounts/{id}/inboxes/{iid}/set_agent_bot``

Wire shape mirrors `_agent_bot.json.jbuilder`:
  * single resource → bare object (NO ``payload`` wrap)
  * collection      → top-level array
  * destroy         → ``head :ok`` (200, empty body)
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import (
    AccountContext,
    account_context,
    require_admin,
)
from app.core.errors import ChatwootHTTPException
from app.domains.agent_bots.models import AgentBot
from app.domains.agent_bots.presenters import present_agent_bot
from app.domains.agent_bots.schemas import (
    AgentBotPayload,
    SetAgentBotPayload,
)
from app.domains.agent_bots.service import (
    attach_bot_to_inbox,
    create_bot,
    destroy_bot,
    detach_bot_from_inbox,
    fetch_account_bot,
    list_bots_accessible_to,
    reset_bot_secret,
    update_bot,
)
from app.domains.inboxes.models import Inbox
from sqlmodel import select

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/agent_bots",
    tags=["agent-bots"],
)

# Inbox-side attach lives under a different prefix.
inbox_set_agent_bot_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/inboxes/{inbox_id}",
    tags=["agent-bots"],
)


async def _find_for_write(
    session: AsyncSession, *, account_id: int, bot_id: int
) -> AgentBot:
    bot = await fetch_account_bot(
        session, account_id=account_id, bot_id=bot_id
    )
    if bot is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return bot


async def _find_for_read(
    session: AsyncSession, *, account_id: int, bot_id: int
) -> AgentBot:
    """Read-side lookup: include system bots (``account_id IS NULL``)."""
    bot = await session.get(AgentBot, bot_id)
    if bot is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    if bot.account_id is not None and bot.account_id != account_id:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return bot


# ===========================================================================
# CRUD
# ===========================================================================
@router.get("")
async def index_bots(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await list_bots_accessible_to(
        session, account_id=ctx.account.id
    )
    show_secret = ctx.is_administrator
    return [
        present_agent_bot(b, show_secret=show_secret) for b in rows
    ]


@router.post("", status_code=status.HTTP_200_OK)
async def create_bot_endpoint(
    payload: AgentBotPayload,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    body = payload.model_dump(exclude_unset=True)
    bot = await create_bot(
        session, account_id=ctx.account.id, payload=body
    )
    return present_agent_bot(bot, show_secret=True)


@router.get("/{bot_id}")
async def show_bot(
    bot_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    bot = await _find_for_read(
        session, account_id=ctx.account.id, bot_id=bot_id
    )
    return present_agent_bot(bot, show_secret=ctx.is_administrator)


@router.patch("/{bot_id}")
async def update_bot_endpoint(
    bot_id: Annotated[int, Path()],
    payload: AgentBotPayload,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    bot = await _find_for_write(
        session, account_id=ctx.account.id, bot_id=bot_id
    )
    body = payload.model_dump(exclude_unset=True)
    updated = await update_bot(session, bot=bot, payload=body)
    return present_agent_bot(updated, show_secret=True)


@router.delete("/{bot_id}", status_code=status.HTTP_200_OK)
async def destroy_bot_endpoint(
    bot_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    bot = await _find_for_write(
        session, account_id=ctx.account.id, bot_id=bot_id
    )
    await destroy_bot(session, bot=bot)
    return {}


@router.post("/{bot_id}/reset_secret", status_code=status.HTTP_200_OK)
async def reset_secret_endpoint(
    bot_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    bot = await _find_for_write(
        session, account_id=ctx.account.id, bot_id=bot_id
    )
    rotated = await reset_bot_secret(session, bot=bot)
    return present_agent_bot(rotated, show_secret=True)


# ===========================================================================
# Inbox-side attach/detach
# ===========================================================================
async def _find_inbox(
    session: AsyncSession, *, account_id: int, inbox_id: int
) -> Inbox:
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.id == inbox_id, Inbox.account_id == account_id
            )
        )
    ).first()
    if inbox is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return inbox


@inbox_set_agent_bot_router.post(
    "/set_agent_bot", status_code=status.HTTP_200_OK
)
async def set_agent_bot(
    inbox_id: Annotated[int, Path()],
    payload: SetAgentBotPayload,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /inboxes/{id}/set_agent_bot`` — attach a bot.

    ``agent_bot=null`` detaches; any other id attaches (replacing any
    prior bot since Chatwoot enforces one-per-inbox)."""
    assert ctx.account.id is not None
    inbox = await _find_inbox(
        session, account_id=ctx.account.id, inbox_id=inbox_id
    )
    if payload.agent_bot is None:
        await detach_bot_from_inbox(session, inbox=inbox)
    else:
        await attach_bot_to_inbox(
            session,
            account_id=ctx.account.id,
            inbox=inbox,
            agent_bot_id=payload.agent_bot,
        )
    return {}


@inbox_set_agent_bot_router.delete(
    "/set_agent_bot", status_code=status.HTTP_200_OK
)
async def delete_agent_bot(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    inbox = await _find_inbox(
        session, account_id=ctx.account.id, inbox_id=inbox_id
    )
    await detach_bot_from_inbox(session, inbox=inbox)
    return {}


__all__ = ["inbox_set_agent_bot_router", "router"]
