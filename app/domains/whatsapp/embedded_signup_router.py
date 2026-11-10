"""WhatsApp Embedded Signup endpoints (F2 multitenant).

* ``GET  /api/v1/accounts/{id}/whatsapp/embedded_signup`` — what the
  "Conectar WhatsApp" button needs (app id, configuration id) and which
  installation settings are missing.
* ``POST /api/v1/accounts/{id}/whatsapp/embedded_signup`` — the popup's
  ``code`` + ``waba_id`` + ``phone_number_id`` → the connected inbox.

Admin only, like the other channel connections.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.domains.inboxes.presenters import present_inbox
from app.domains.whatsapp import embedded_signup

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/whatsapp/embedded_signup",
    tags=["whatsapp-embedded-signup"],
)


class EmbeddedSignupRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    waba_id: str
    phone_number_id: str


@router.get("")
async def embedded_signup_info(
    ctx: Annotated[AccountContext, Depends(require_admin)],
) -> dict[str, Any]:
    return embedded_signup.signup_info()


@router.post("", status_code=status.HTTP_200_OK)
async def embedded_signup_connect(
    payload: EmbeddedSignupRequest,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    inbox, channel, created = await embedded_signup.connect_number(
        session,
        account=ctx.account,
        code=payload.code.strip(),
        waba_id=payload.waba_id.strip(),
        phone_number_id=payload.phone_number_id.strip(),
    )
    return {
        "created": created,
        "inbox": present_inbox(inbox, channel=channel, is_administrator=True),
    }


__all__ = ["router"]
