"""AssignmentPolicy HTTP endpoints.

Ports two Rails controllers:

  * ``Api::V1::Accounts::AssignmentPoliciesController`` — the CRUD surface.
  * ``Api::V1::Accounts::Inboxes::AssignmentPoliciesController`` — the
    singular per-inbox link (``resource :assignment_policy``).

Route map::

  GET    /api/v1/accounts/{id}/assignment_policies            index
  POST   /api/v1/accounts/{id}/assignment_policies            create
  GET    /api/v1/accounts/{id}/assignment_policies/{pid}      show
  PATCH  /api/v1/accounts/{id}/assignment_policies/{pid}      update
  DELETE /api/v1/accounts/{id}/assignment_policies/{pid}      destroy → head :ok

  GET    /api/v1/accounts/{id}/inboxes/{iid}/assignment_policy   show
  POST   /api/v1/accounts/{id}/inboxes/{iid}/assignment_policy   create
  DELETE /api/v1/accounts/{id}/inboxes/{iid}/assignment_policy   destroy → head :ok

Authorisation: every action requires ``@account_user.administrator?``
(``AssignmentPolicyPolicy`` gates all five methods on admin). Wire shape:
bare ``render json:`` — single objects and the index array are unwrapped.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.assignment_policies.models import AssignmentPolicy
from app.domains.assignment_policies.presenters import (
    present_assignment_policies,
    present_assignment_policy,
)
from app.domains.assignment_policies.schemas import (
    AssignmentPolicyEnvelope,
    InboxPolicyLinkBody,
)
from app.domains.assignment_policies.service import (
    create_policy,
    destroy_policy,
    get_inbox_policy,
    get_policy,
    list_policies,
    remove_inbox_policy,
    set_inbox_policy,
    update_policy,
)
from app.domains.inboxes.models import Inbox

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/assignment_policies",
    tags=["assignment_policies"],
)

inbox_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/inboxes/{inbox_id}/assignment_policy",
    tags=["assignment_policies"],
)


def _not_found() -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=404, detail={"error": "Resource could not be found"}
    )


async def _find_policy(
    session: AsyncSession, ctx: AccountContext, policy_id: int
) -> AssignmentPolicy:
    assert ctx.account.id is not None
    policy = await get_policy(
        session, account_id=ctx.account.id, policy_id=policy_id
    )
    if policy is None:
        raise _not_found()
    return policy


async def _find_inbox(
    session: AsyncSession, ctx: AccountContext, inbox_id: int
) -> Inbox:
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.id == inbox_id, Inbox.account_id == ctx.account.id
            )
        )
    ).first()
    if inbox is None:
        raise _not_found()
    return inbox


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
@router.get("")
async def index_assignment_policies(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await list_policies(session, account_id=ctx.account.id)
    return present_assignment_policies(rows)


@router.post("", status_code=status.HTTP_200_OK)
async def create_assignment_policy(
    payload: AssignmentPolicyEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    body = payload.assignment_policy.model_dump(exclude_unset=True)
    policy = await create_policy(session, account_id=ctx.account.id, payload=body)
    return present_assignment_policy(policy)


@router.get("/{policy_id}")
async def show_assignment_policy(
    policy_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    policy = await _find_policy(session, ctx, policy_id)
    return present_assignment_policy(policy)


@router.patch("/{policy_id}")
async def update_assignment_policy(
    policy_id: Annotated[int, Path()],
    payload: AssignmentPolicyEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    policy = await _find_policy(session, ctx, policy_id)
    body = payload.assignment_policy.model_dump(exclude_unset=True)
    updated = await update_policy(session, policy=policy, payload=body)
    return present_assignment_policy(updated)


@router.delete("/{policy_id}", status_code=status.HTTP_200_OK)
async def destroy_assignment_policy(
    policy_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE`` → Rails ``head :ok`` (HTTP 200, empty body)."""
    policy = await _find_policy(session, ctx, policy_id)
    await destroy_policy(session, policy=policy)
    return {}


# ---------------------------------------------------------------------------
# Inbox link (singular resource)
# ---------------------------------------------------------------------------
@inbox_router.get("")
async def show_inbox_assignment_policy(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    await _find_inbox(session, ctx, inbox_id)
    policy = await get_inbox_policy(session, inbox_id=inbox_id)
    if policy is None:
        # Rails: ``render_not_found_error(t('errors.assignment_policy.not_found'))``
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Assignment policy not found"}
        )
    return present_assignment_policy(policy)


@inbox_router.post("", status_code=status.HTTP_200_OK)
async def create_inbox_assignment_policy(
    inbox_id: Annotated[int, Path()],
    payload: InboxPolicyLinkBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Attach a policy to the inbox, replacing any existing one."""
    await _find_inbox(session, ctx, inbox_id)
    policy = await _find_policy(session, ctx, payload.assignment_policy_id)
    await set_inbox_policy(session, inbox_id=inbox_id, policy=policy)
    return present_assignment_policy(policy)


@inbox_router.delete("", status_code=status.HTTP_200_OK)
async def destroy_inbox_assignment_policy(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE`` → Rails ``head :ok`` (HTTP 200, empty body)."""
    await _find_inbox(session, ctx, inbox_id)
    await remove_inbox_policy(session, inbox_id=inbox_id)
    return {}


__all__ = ["inbox_router", "router"]
