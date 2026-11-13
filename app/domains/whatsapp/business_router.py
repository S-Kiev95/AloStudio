"""WhatsApp number management endpoints (F5), next to the templates ones:

  * ``GET  .../whatsapp/phone``              — the number's state on Meta.
  * ``GET  .../whatsapp/profile``            — the business profile.
  * ``POST .../whatsapp/profile``            — change it (admin).
  * ``POST .../whatsapp/profile/photo``      — new profile photo (admin).
  * ``GET  .../whatsapp/qr``                 — QR codes and short links.
  * ``POST .../whatsapp/qr``                 — create one (admin).
  * ``POST .../whatsapp/qr/{code}``          — change its message (admin).
  * ``DELETE .../whatsapp/qr/{code}``        — delete it (admin).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Path, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.domains.whatsapp.business import (
    delete_qr_code,
    get_profile,
    list_qr_codes,
    phone_status,
    save_qr_code,
    update_profile,
    update_profile_photo,
)
from app.domains.whatsapp.templates_router import _whatsapp_channel

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/inboxes/{inbox_id}/whatsapp",
    tags=["whatsapp-business"],
)


class ProfileBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    about: str | None = None
    address: str | None = None
    description: str | None = None
    email: str | None = None
    websites: list[str] | None = None
    vertical: str | None = None


class QrBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prefilled_message: str = ""


async def _channel(session: AsyncSession, ctx: AccountContext, inbox_id: int):
    assert ctx.account.id is not None
    return await _whatsapp_channel(session, account_id=ctx.account.id, inbox_id=inbox_id)


@router.get("/phone")
async def phone_endpoint(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    return await phone_status(await _channel(session, ctx, inbox_id))


@router.get("/profile")
async def profile_endpoint(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    return await get_profile(await _channel(session, ctx, inbox_id))


@router.post("/profile")
async def update_profile_endpoint(
    inbox_id: Annotated[int, Path()],
    body: ProfileBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    channel = await _channel(session, ctx, inbox_id)
    return await update_profile(channel, body.model_dump(exclude_none=True))


@router.post("/profile/photo")
async def update_profile_photo_endpoint(
    inbox_id: Annotated[int, Path()],
    file: Annotated[UploadFile, File()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    channel = await _channel(session, ctx, inbox_id)
    content = await file.read()
    return await update_profile_photo(
        channel, content=content, content_type=file.content_type or ""
    )


@router.get("/qr")
async def qr_list_endpoint(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    return {"qr_codes": await list_qr_codes(await _channel(session, ctx, inbox_id))}


@router.post("/qr")
async def qr_create_endpoint(
    inbox_id: Annotated[int, Path()],
    body: QrBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    channel = await _channel(session, ctx, inbox_id)
    return {"qr_codes": await save_qr_code(channel, message=body.prefilled_message)}


@router.post("/qr/{code}")
async def qr_update_endpoint(
    inbox_id: Annotated[int, Path()],
    code: Annotated[str, Path()],
    body: QrBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    channel = await _channel(session, ctx, inbox_id)
    return {
        "qr_codes": await save_qr_code(channel, message=body.prefilled_message, code=code)
    }


@router.delete("/qr/{code}")
async def qr_delete_endpoint(
    inbox_id: Annotated[int, Path()],
    code: Annotated[str, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    channel = await _channel(session, ctx, inbox_id)
    return {"qr_codes": await delete_qr_code(channel, code=code)}


__all__ = ["router"]
