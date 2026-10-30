"""Agent chat HTTP endpoints (any member of the account; each user sees
only their own chats, and what the agent may do follows their role).

Route map:
  * ``GET    /api/v1/accounts/{account_id}/agent``
  * ``GET    /api/v1/accounts/{account_id}/agent/threads``
  * ``POST   /api/v1/accounts/{account_id}/agent/threads``
  * ``GET    /api/v1/accounts/{account_id}/agent/threads/{thread_id}``
  * ``DELETE /api/v1/accounts/{account_id}/agent/threads/{thread_id}``
  * ``POST   /api/v1/accounts/{account_id}/agent/threads/{thread_id}/messages``
  * ``POST   /api/v1/accounts/{account_id}/agent/threads/{thread_id}/actions/{action_id}/confirm``
  * ``POST   /api/v1/accounts/{account_id}/agent/threads/{thread_id}/actions/{action_id}/reject``

A turn is answered in the same request (no streaming): it can take tens of
seconds while the model calls tools. Every write it proposes waits for the
user's confirmation.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.domains.agent import service as svc
from app.domains.agent.models import AgentThread
from app.domains.agent.presenters import present_thread, present_thread_summary
from app.domains.agent.schemas import AgentMessageIn

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/agent",
    tags=["agent"],
)


async def _thread_response(
    session: AsyncSession, ctx: AccountContext, thread: AgentThread
) -> dict[str, Any]:
    rows = await svc.thread_messages(session, thread.id)  # type: ignore[arg-type]
    return await present_thread(session, ctx, thread, rows)


@router.get("")
async def agent_status(
    ctx: Annotated[AccountContext, Depends(account_context)],
) -> dict[str, Any]:
    return {
        "enabled": svc.agent_enabled(),
        "model": get_settings().openai_agent_model,
        "can_write": ctx.is_administrator,
    }


@router.get("/threads")
async def list_threads_endpoint(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    threads = await svc.list_threads(session, ctx)
    pending = await svc.pending_thread_ids(session, [t.id for t in threads])  # type: ignore[misc]
    return {
        "threads": [
            present_thread_summary(t, has_pending_action=t.id in pending) for t in threads
        ]
    }


@router.post("/threads", status_code=status.HTTP_200_OK)
async def create_thread_endpoint(
    payload: AgentMessageIn,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    thread = await svc.start_thread(
        session, ctx, content=payload.content, timezone=payload.timezone
    )
    return await _thread_response(session, ctx, thread)


@router.get("/threads/{thread_id}")
async def get_thread_endpoint(
    thread_id: int,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    thread = await svc.get_thread(session, ctx, thread_id)
    return await _thread_response(session, ctx, thread)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_200_OK)
async def delete_thread_endpoint(
    thread_id: int,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    thread = await svc.get_thread(session, ctx, thread_id)
    await svc.delete_thread(session, thread)
    return {}


@router.post("/threads/{thread_id}/messages", status_code=status.HTTP_200_OK)
async def send_message_endpoint(
    thread_id: int,
    payload: AgentMessageIn,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    thread = await svc.get_thread(session, ctx, thread_id)
    await svc.send_message(
        session, ctx, thread, content=payload.content, timezone=payload.timezone
    )
    return await _thread_response(session, ctx, thread)


@router.post(
    "/threads/{thread_id}/actions/{action_id}/confirm", status_code=status.HTTP_200_OK
)
async def confirm_action_endpoint(
    thread_id: int,
    action_id: str,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    thread = await svc.get_thread(session, ctx, thread_id)
    await svc.confirm_action(session, ctx, thread, action_id)
    return await _thread_response(session, ctx, thread)


@router.post(
    "/threads/{thread_id}/actions/{action_id}/reject", status_code=status.HTTP_200_OK
)
async def reject_action_endpoint(
    thread_id: int,
    action_id: str,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    thread = await svc.get_thread(session, ctx, thread_id)
    await svc.reject_action(session, ctx, thread, action_id)
    return await _thread_response(session, ctx, thread)


__all__ = ["router"]
