"""AutomationRule HTTP endpoints.

Ports ``Api::V1::Accounts::AutomationRulesController``.

Route map:

  * ``GET    /api/v1/accounts/{id}/automation_rules``           — admin only
  * ``POST   /api/v1/accounts/{id}/automation_rules``           — admin only
  * ``GET    /api/v1/accounts/{id}/automation_rules/{id}``      — admin only
  * ``PATCH  /api/v1/accounts/{id}/automation_rules/{id}``      — admin only
  * ``DELETE /api/v1/accounts/{id}/automation_rules/{id}``      — admin only
                                                                  (head :ok)
  * ``POST   /api/v1/accounts/{id}/automation_rules/{id}/clone`` — admin only

Wire shape (matches Chatwoot's jbuilders byte-for-byte, including
the inconsistency where ``create`` returns the bare object while
``show`` / ``update`` / ``index`` / ``clone`` wrap in ``payload``):

  * ``index``        → ``{"payload": [<rule>, ...]}``
  * ``create``       → bare ``<rule>`` (NO envelope)
  * ``show``         → ``{"payload": <rule>}``
  * ``update``       → ``{"payload": <rule>}``
  * ``clone``        → ``{"payload": <rule>}``
  * ``destroy``      → ``head :ok`` (200, empty body)
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.automation.presenters import envelope_payload, present_rule
from app.domains.automation.schemas import AutomationRulePayload
from app.domains.automation.service import (
    clone_rule,
    create_rule,
    destroy_rule,
    fetch_rule,
    list_rules,
    update_rule,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/automation_rules",
    tags=["automation-rules"],
)


# ============================================================================
# Helpers
# ============================================================================
async def _find(
    session: AsyncSession, *, account_id: int, rule_id: int
):
    rule = await fetch_rule(
        session, account_id=account_id, rule_id=rule_id
    )
    if rule is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return rule


# ============================================================================
# CRUD
# ============================================================================
@router.get("")
async def index_rules(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    rows = await list_rules(session, account_id=ctx.account.id)
    return envelope_payload([present_rule(r) for r in rows])


@router.post("", status_code=status.HTTP_200_OK)
async def create_rule_endpoint(
    payload: AutomationRulePayload,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST`` returns the bare object — Rails' ``create.json.jbuilder``
    does not wrap. (``show``/``update`` do.)"""
    assert ctx.account.id is not None
    body = payload.model_dump(exclude_unset=True)
    rule = await create_rule(
        session, account_id=ctx.account.id, payload=body
    )
    return present_rule(rule)


@router.get("/{rule_id}")
async def show_rule(
    rule_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    rule = await _find(session, account_id=ctx.account.id, rule_id=rule_id)
    return envelope_payload(present_rule(rule))


@router.patch("/{rule_id}")
async def update_rule_endpoint(
    rule_id: Annotated[int, Path()],
    payload: AutomationRulePayload,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    rule = await _find(session, account_id=ctx.account.id, rule_id=rule_id)
    body = payload.model_dump(exclude_unset=True)
    updated = await update_rule(session, rule=rule, payload=body)
    return envelope_payload(present_rule(updated))


@router.delete("/{rule_id}", status_code=status.HTTP_200_OK)
async def destroy_rule_endpoint(
    rule_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE`` → Rails ``head :ok`` (HTTP 200, empty body)."""
    assert ctx.account.id is not None
    rule = await _find(session, account_id=ctx.account.id, rule_id=rule_id)
    await destroy_rule(session, rule=rule)
    return {}


@router.post("/{rule_id}/clone", status_code=status.HTTP_200_OK)
async def clone_rule_endpoint(
    rule_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    rule = await _find(session, account_id=ctx.account.id, rule_id=rule_id)
    cloned = await clone_rule(session, rule=rule)
    return envelope_payload(present_rule(cloned))


__all__ = ["router"]
