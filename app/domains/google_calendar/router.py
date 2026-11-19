"""Google Calendar for the signed-in user (F17).

Route map, under ``/api/v1/profile/google_calendar``:
  * ``GET``                 — available, connected, the address, last sync
  * ``GET /authorize_url``  — Google's consent screen for this user
  * ``POST``                — ``{code, state}`` from the callback: connect
  * ``DELETE``              — disconnect (our events leave their calendar)

Errors carry ``code`` (``google_calendar.<code>``).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user
from app.core.errors import ChatwootHTTPException
from app.domains.google_calendar import service
from app.domains.users.models import User

router = APIRouter(prefix="/api/v1/profile/google_calendar", tags=["google_calendar"])


class ConnectBody(BaseModel):
    code: str
    state: str


def _fail(code: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=422, detail={"message": code, "code": f"google_calendar.{code}"}
    )


@router.get("")
async def show(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    assert user.id is not None
    return await service.status(session, user.id)


@router.get("/authorize_url")
async def authorize_url(user: User = Depends(current_user)) -> dict[str, str]:
    if not service.available():
        raise _fail("unavailable")
    assert user.id is not None
    return {"url": service.authorize_url(user.id)}


@router.post("")
async def connect(
    body: ConnectBody,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if not service.available():
        raise _fail("unavailable")
    assert user.id is not None
    try:
        await service.connect(session, user_id=user.id, code=body.code, state=body.state)
    except ValueError as exc:
        raise _fail(str(exc)) from exc
    return await service.status(session, user.id)


@router.delete("")
async def disconnect(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    assert user.id is not None
    await service.disconnect(session, user.id)
    return await service.status(session, user.id)
