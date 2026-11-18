"""Handoff responsibles (PLAN.agente-ia.md, 2a). Administrators only.

Route map, under ``/api/v1/accounts/{account_id}/handoff``:
  * ``GET  ""``                     — the account's rule, the label rules in
    order and whether AloStudio's AI can be chosen
  * ``PUT  ""``                     — ``{account: {user_id, to_ai}, labels:
    [{label_id, user_id, to_ai}]}``, labels in priority order; replaces
    both at once (an empty account target clears it)
  * ``GET  /contacts/{contact_id}`` — the chat's rule
  * ``PUT  /contacts/{contact_id}`` — ``{user_id, to_ai}`` (both empty clears)

The inbox level is the inbox's ``handoff_assignee_id`` (Ajustes →
Bandejas). Errors carry ``code`` (``handoff.<code>``) for the panel.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.contacts.models import Contact
from app.domains.handoff import service

router = APIRouter(prefix="/api/v1/accounts/{account_id}/handoff", tags=["handoff"])

_NOT_FOUND = {"error": "Resource could not be found"}


class TargetBody(BaseModel):
    user_id: int | None = None
    to_ai: bool = False


class LabelRuleBody(TargetBody):
    label_id: int


class RulesBody(BaseModel):
    account: TargetBody
    labels: list[LabelRuleBody]


def _account_id(ctx: AccountContext) -> int:
    assert ctx.account.id is not None
    return ctx.account.id


def _fail(code: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=422, detail={"message": code, "code": f"handoff.{code}"}
    )


async def _contact(session: AsyncSession, ctx: AccountContext, contact_id: int) -> Contact:
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.account_id != _account_id(ctx):
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    return contact


@router.get("")
async def show_rules(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    return await service.present_rules(session, _account_id(ctx))


@router.put("")
async def update_rules(
    body: RulesBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    try:
        return await service.save_rules(
            session,
            account_id=_account_id(ctx),
            account=body.account.model_dump(),
            labels=[rule.model_dump() for rule in body.labels],
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc


@router.get("/contacts/{contact_id}")
async def show_contact_rule(
    contact_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    contact = await _contact(session, ctx, contact_id)
    return await service.present_contact_rule(session, contact)


@router.put("/contacts/{contact_id}")
async def update_contact_rule(
    contact_id: Annotated[int, Path()],
    body: TargetBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    contact = await _contact(session, ctx, contact_id)
    try:
        target = await service.save_contact_rule(
            session, contact=contact, user_id=body.user_id, to_ai=body.to_ai
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc
    return {"contact": target}


__all__ = ["router"]
