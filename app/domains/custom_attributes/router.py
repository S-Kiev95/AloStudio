"""CustomAttributeDefinition HTTP endpoints.

Ports ``Api::V1::Accounts::CustomAttributeDefinitionsController``.

Route map:

  * ``GET    /api/v1/accounts/:account_id/custom_attribute_definitions``
  * ``POST   /api/v1/accounts/:account_id/custom_attribute_definitions``
  * ``GET    /api/v1/accounts/:account_id/custom_attribute_definitions/:id``
  * ``PATCH  /api/v1/accounts/:account_id/custom_attribute_definitions/:id``
  * ``DELETE /api/v1/accounts/:account_id/custom_attribute_definitions/:id``

Authorisation: Chatwoot's controller does **not** invoke Pundit — there's
no ``custom_attribute_definition_policy.rb``. Every account member can
CRUD definitions. We match: ``account_context`` (not ``require_admin``).

Wire shape:
  * ``index`` → top-level JSON array.
  * ``show`` / ``create`` / ``update`` → bare definition object.
  * ``destroy`` → empty body, 204 (``head :no_content``).

``attribute_model`` filter on index: Chatwoot reads
``permitted_params[:attribute_model]`` and scopes with
``.with_attribute_model(key)`` — when the param is missing the scope
returns all rows. We accept the string enum (``"contact_attribute"`` /
``"conversation_attribute"``) and translate at the service boundary.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.custom_attributes.models import (
    CustomAttributeDefinition,
    attr_model_from_str,
)
from app.domains.custom_attributes.presenters import (
    present_definition,
    present_definitions_index,
)
from app.domains.custom_attributes.schemas import (
    AttributeModelLiteral,
    CustomAttributeDefinitionEnvelope,
)
from app.domains.custom_attributes.service import (
    create_definition,
    update_definition,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/custom_attribute_definitions",
    tags=["custom_attributes"],
)


# ============================================================================
# CRUD
# ============================================================================
@router.get("")
async def index_definitions(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    attribute_model: AttributeModelLiteral | None = Query(None),
) -> list[dict[str, Any]]:
    """``GET /custom_attribute_definitions`` — optionally filtered by model.

    Rails' ``with_attribute_model`` scope bypasses the filter when the
    value is missing. We mirror: no param → no WHERE clause.
    """
    assert ctx.account.id is not None
    stmt = select(CustomAttributeDefinition).where(
        CustomAttributeDefinition.account_id == ctx.account.id
    )
    if attribute_model is not None:
        stmt = stmt.where(
            CustomAttributeDefinition.attribute_model
            == attr_model_from_str(attribute_model)
        )
    stmt = stmt.order_by(CustomAttributeDefinition.id.desc())  # type: ignore[attr-defined]
    rows = list((await session.exec(stmt)).all())
    return present_definitions_index(rows)


@router.post("", status_code=status.HTTP_200_OK)
async def create_definition_endpoint(
    payload: CustomAttributeDefinitionEnvelope,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /custom_attribute_definitions``.

    Body is wrapped in ``{"custom_attribute_definition": {...}}`` per
    ``params.require(:custom_attribute_definition)``. 200-not-201 keeps
    parity with Rails' default create response.
    """
    body = payload.custom_attribute_definition.model_dump(exclude_none=True)
    row = await create_definition(
        session,
        account_id=ctx.account.id,  # type: ignore[arg-type]
        payload=body,
    )
    return present_definition(row)


@router.get("/{definition_id}")
async def show_definition(
    definition_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_definition(session, ctx, definition_id)
    return present_definition(row)


@router.patch("/{definition_id}")
async def update_definition_endpoint(
    definition_id: Annotated[int, Path()],
    payload: CustomAttributeDefinitionEnvelope,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_definition(session, ctx, definition_id)
    body = payload.custom_attribute_definition.model_dump(exclude_none=True)
    updated = await update_definition(session, definition=row, payload=body)
    return present_definition(updated)


@router.delete("/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy_definition(
    definition_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """``DELETE /custom_attribute_definitions/:id`` → ``head :no_content``."""
    row = await _find_definition(session, ctx, definition_id)
    await session.delete(row)
    await session.flush()
    return None


# ============================================================================
# Helpers
# ============================================================================
async def _find_definition(
    session: AsyncSession, ctx: AccountContext, definition_id: int
) -> CustomAttributeDefinition:
    stmt = select(CustomAttributeDefinition).where(
        CustomAttributeDefinition.id == definition_id,
        CustomAttributeDefinition.account_id == ctx.account.id,
    )
    row = (await session.exec(stmt)).first()
    if row is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return row
