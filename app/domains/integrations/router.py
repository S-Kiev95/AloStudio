"""Integration apps + hooks HTTP endpoints.

Ports ``Api::V1::Accounts::Integrations::AppsController`` +
``Api::V1::Accounts::Integrations::HooksController``.

Route map:

  * ``GET    /api/v1/accounts/{id}/integrations/apps``       — admin OR agent
  * ``GET    /api/v1/accounts/{id}/integrations/apps/{id}``  — admin OR agent
  * ``POST   /api/v1/accounts/{id}/integrations/hooks``      — admin only
  * ``PATCH  /api/v1/accounts/{id}/integrations/hooks/{id}`` — admin only
  * ``DELETE /api/v1/accounts/{id}/integrations/hooks/{id}`` — admin only (head :ok)

``process_event`` (the per-vendor inbound trigger) defers to follow-up
phases on a vendor-by-vendor basis — Phase 8.4 is the registry, not
the runtime.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import Inbox
from app.domains.integrations.models import (
    INTEGRATION_APPS,
    find_app,
)
from app.domains.integrations.presenters import (
    present_app,
    present_hook,
)
from app.domains.integrations.schemas import HookEnvelope
from app.domains.integrations.service import (
    create_hook,
    destroy_hook,
    fetch_hook,
    list_hooks,
    update_hook,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/integrations",
    tags=["integrations"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _resolve_inbox(
    session: AsyncSession, inbox_id: int | None
) -> Inbox | None:
    if inbox_id is None:
        return None
    return await session.get(Inbox, inbox_id)


async def _present_hook(
    session: AsyncSession,
    hook,
    *,
    show_admin_fields: bool,
) -> dict[str, Any]:
    inbox = await _resolve_inbox(session, hook.inbox_id)
    return present_hook(
        hook, inbox=inbox, show_admin_fields=show_admin_fields
    )


# ===========================================================================
# Apps
# ===========================================================================
@router.get("/apps")
async def index_apps(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``GET /apps`` — static catalogue + each account's hooks.

    Wire shape mirrors Chatwoot: ``{"payload": [<app>, ...]}``."""
    assert ctx.account.id is not None
    hooks = await list_hooks(session, account_id=ctx.account.id)
    bodies = [
        present_app(
            app,
            account_hooks=hooks,
            show_admin_fields=ctx.is_administrator,
        )
        for app in INTEGRATION_APPS
    ]
    return {"payload": bodies}


@router.get("/apps/{app_id}")
async def show_app(
    app_id: Annotated[str, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    app = find_app(app_id)
    if app is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    hooks = await list_hooks(session, account_id=ctx.account.id)
    return present_app(
        app,
        account_hooks=hooks,
        show_admin_fields=ctx.is_administrator,
    )


# ===========================================================================
# Hooks
# ===========================================================================
@router.post("/hooks", status_code=status.HTTP_200_OK)
async def create_hook_endpoint(
    payload: HookEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    body = payload.hook.model_dump(exclude_unset=True)
    hook = await create_hook(
        session, account_id=ctx.account.id, payload=body
    )
    return await _present_hook(
        session, hook, show_admin_fields=True
    )


@router.patch("/hooks/{hook_id}")
async def update_hook_endpoint(
    hook_id: Annotated[int, Path()],
    payload: HookEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    hook = await fetch_hook(
        session, account_id=ctx.account.id, hook_id=hook_id
    )
    if hook is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    body = payload.hook.model_dump(exclude_unset=True)
    updated = await update_hook(session, hook=hook, payload=body)
    return await _present_hook(
        session, updated, show_admin_fields=True
    )


@router.delete(
    "/hooks/{hook_id}", status_code=status.HTTP_200_OK
)
async def destroy_hook_endpoint(
    hook_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    hook = await fetch_hook(
        session, account_id=ctx.account.id, hook_id=hook_id
    )
    if hook is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    await destroy_hook(session, hook=hook)
    return {}


__all__ = ["router"]
