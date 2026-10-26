"""Appointments HTTP endpoints (admin OR agent read & write).

Route map:
  * ``GET    /api/v1/accounts/{account_id}/appointments``
  * ``POST   /api/v1/accounts/{account_id}/appointments``
  * ``GET    /api/v1/accounts/{account_id}/appointments/{appointment_id}``
  * ``PATCH  /api/v1/accounts/{account_id}/appointments/{appointment_id}``
  * ``DELETE /api/v1/accounts/{account_id}/appointments/{appointment_id}``
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.appointments import service as svc
from app.domains.appointments.models import Appointment
from app.domains.appointments.presenters import (
    present_appointments,
    present_one_appointment,
)
from app.domains.appointments.schemas import (
    AppointmentCreate,
    AppointmentUpdate,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/appointments",
    tags=["appointments"],
)


async def _find_appointment(
    session: AsyncSession, ctx: AccountContext, appointment_id: int
) -> Appointment:
    assert ctx.account.id is not None
    row = await svc.get_appointment(
        session, account_id=ctx.account.id, appointment_id=appointment_id
    )
    if row is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return row


@router.get("")
async def index_appointments(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
    contact_id: int | None = None,
    status: str | None = None,
    page: int = 1,
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await svc.list_appointments(
        session,
        account_id=ctx.account.id,
        starts_from=from_,
        starts_to=to,
        contact_id=contact_id,
        status=status,
        page=page,
    )
    return await present_appointments(session, rows)


@router.post("", status_code=status.HTTP_200_OK)
async def create_appointment_endpoint(
    payload: AppointmentCreate,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    row = await svc.create_appointment(
        session,
        account_id=ctx.account.id,
        payload=payload.model_dump(exclude_unset=True),
        created_by_id=ctx.user.id,
    )
    return await present_one_appointment(session, row)


@router.get("/{appointment_id}")
async def show_appointment(
    appointment_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_appointment(session, ctx, appointment_id)
    return await present_one_appointment(session, row)


@router.patch("/{appointment_id}")
async def update_appointment_endpoint(
    appointment_id: Annotated[int, Path()],
    payload: AppointmentUpdate,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_appointment(session, ctx, appointment_id)
    updated = await svc.update_appointment(
        session,
        appointment=row,
        payload=payload.model_dump(exclude_unset=True),
    )
    return await present_one_appointment(session, updated)


@router.delete("/{appointment_id}", status_code=status.HTTP_200_OK)
async def delete_appointment_endpoint(
    appointment_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_appointment(session, ctx, appointment_id)
    await svc.delete_appointment(session, appointment=row)
    return {}


__all__ = ["router"]
