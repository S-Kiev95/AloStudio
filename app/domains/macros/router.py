"""Macro HTTP endpoints.

Ports ``Api::V1::Accounts::MacrosController``.

Route map:

  * ``GET    /api/v1/accounts/{id}/macros``
  * ``POST   /api/v1/accounts/{id}/macros``
  * ``GET    /api/v1/accounts/{id}/macros/{id}``
  * ``PATCH  /api/v1/accounts/{id}/macros/{id}``
  * ``DELETE /api/v1/accounts/{id}/macros/{id}``      → ``head :ok`` (200)
  * ``POST   /api/v1/accounts/{id}/macros/{id}/execute`` → ``head :ok`` (200)

Authorisation per ``MacroPolicy`` (see ``service.can_user_*``). Index
+ create are open to any account member; show / update / destroy /
execute fall back to the per-record policy. Unauthorised attempts get
a 401 with the canonical Pundit body.

Wire shape:
  * Single resource → ``{"payload": {<macro>}}``.
  * Collection      → ``{"payload": [<macro>, ...]}``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.presenters import present_agent
from app.domains.macros.models import Macro
from app.domains.macros.presenters import (
    envelope_index,
    envelope_one,
    present_macro,
)
from app.domains.macros.schemas import MacroExecutePayload, MacroPayload
from app.domains.macros.service import (
    can_user_destroy_macro,
    can_user_execute_macro,
    can_user_modify_macro,
    create_macro,
    destroy_macro,
    execute_macro_on_conversations,
    fetch_macro_visible_to_user,
    list_macros_for_user,
    update_macro,
)
from app.domains.users.models import AccountUser, User

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/macros",
    tags=["macros"],
)


# ============================================================================
# Helpers
# ============================================================================
async def _present_user(
    session: AsyncSession, *, account_id: int, user_id: int | None
) -> dict[str, Any] | None:
    """Render an ``_agent.json.jbuilder`` partial for the macro's
    ``created_by`` / ``updated_by`` slots. Returns ``None`` when the
    user is missing — the partial is omitted from the wire."""
    if user_id is None:
        return None
    user = await session.get(User, user_id)
    if user is None:
        return None
    au = (
        await session.exec(
            select(AccountUser).where(
                AccountUser.account_id == account_id,
                AccountUser.user_id == user_id,
            )
        )
    ).first()
    return present_agent(
        account_id=account_id,
        account_user_availability=au.availability if au is not None else None,
        account_user_auto_offline=au.auto_offline if au is not None else None,
        user=user,
    )


async def _present_macro_with_users(
    session: AsyncSession, *, account_id: int, macro: Macro
) -> dict[str, Any]:
    return present_macro(
        macro,
        created_by=await _present_user(
            session, account_id=account_id, user_id=macro.created_by_id
        ),
        updated_by=await _present_user(
            session, account_id=account_id, user_id=macro.updated_by_id
        ),
    )


async def _fetch_for_action(
    session: AsyncSession,
    *,
    account_id: int,
    macro_id: int,
) -> Macro:
    macro = (
        await session.exec(
            select(Macro).where(
                Macro.id == macro_id, Macro.account_id == account_id
            )
        )
    ).first()
    if macro is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return macro


def _denied() -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=401,
        detail={"error": "You are not authorized to do this action"},
    )


# ============================================================================
# CRUD
# ============================================================================
@router.get("")
async def index_macros(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    rows = await list_macros_for_user(
        session, account_id=ctx.account.id, user_id=ctx.user.id
    )
    bodies = [
        await _present_macro_with_users(
            session, account_id=ctx.account.id, macro=m
        )
        for m in rows
    ]
    return envelope_index(bodies)


@router.post("", status_code=status.HTTP_200_OK)
async def create_macro_endpoint(
    payload: MacroPayload,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    body = payload.model_dump(exclude_unset=True)
    macro = await create_macro(
        session,
        account_id=ctx.account.id,
        user_id=ctx.user.id,
        payload=body,
    )
    return envelope_one(
        await _present_macro_with_users(
            session, account_id=ctx.account.id, macro=macro
        )
    )


@router.get("/{macro_id}")
async def show_macro(
    macro_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    macro = await fetch_macro_visible_to_user(
        session,
        account_id=ctx.account.id,
        macro_id=macro_id,
        user_id=ctx.user.id,
    )
    if macro is None:
        # Rails ``check_authorization`` raises Pundit::NotAuthorizedError
        # when the macro exists but isn't visible. The 401-vs-404
        # distinction is hard to replicate without leaking existence —
        # we return 404 on miss and 401 on auth failure separately.
        existing = (
            await session.exec(
                select(Macro).where(
                    Macro.id == macro_id, Macro.account_id == ctx.account.id
                )
            )
        ).first()
        if existing is None:
            raise ChatwootHTTPException(
                status_code=404,
                detail={"error": "Resource could not be found"},
            )
        raise _denied()
    return envelope_one(
        await _present_macro_with_users(
            session, account_id=ctx.account.id, macro=macro
        )
    )


@router.patch("/{macro_id}")
async def update_macro_endpoint(
    macro_id: Annotated[int, Path()],
    payload: MacroPayload,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    macro = await _fetch_for_action(
        session, account_id=ctx.account.id, macro_id=macro_id
    )
    if not await can_user_modify_macro(
        session, macro=macro, user_id=ctx.user.id
    ):
        raise _denied()
    body = payload.model_dump(exclude_unset=True)
    updated = await update_macro(
        session, macro=macro, user_id=ctx.user.id, payload=body
    )
    return envelope_one(
        await _present_macro_with_users(
            session, account_id=ctx.account.id, macro=updated
        )
    )


@router.delete("/{macro_id}", status_code=status.HTTP_200_OK)
async def destroy_macro_endpoint(
    macro_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE /macros/:id`` → Rails ``head :ok`` (HTTP 200, empty body)."""
    assert ctx.account.id is not None and ctx.user.id is not None
    macro = await _fetch_for_action(
        session, account_id=ctx.account.id, macro_id=macro_id
    )
    if not await can_user_destroy_macro(
        session, macro=macro, user_id=ctx.user.id
    ):
        raise _denied()
    await destroy_macro(session, macro=macro)
    return {}


@router.post("/{macro_id}/execute", status_code=status.HTTP_200_OK)
async def execute_macro_endpoint(
    macro_id: Annotated[int, Path()],
    payload: MacroExecutePayload,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /macros/:id/execute`` — Rails enqueues ``MacrosExecutionJob``
    + ``head :ok``. We run inline (see service docstring).
    """
    assert ctx.account.id is not None and ctx.user.id is not None
    macro = await _fetch_for_action(
        session, account_id=ctx.account.id, macro_id=macro_id
    )
    if not await can_user_execute_macro(
        session, macro=macro, user_id=ctx.user.id
    ):
        raise _denied()
    await execute_macro_on_conversations(
        session,
        macro=macro,
        conversation_ids=payload.conversation_ids,
        user_id=ctx.user.id,
    )
    return {}


__all__ = ["router"]
