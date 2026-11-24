"""``/api/v1/accounts/{id}/email_signatures`` — organisation and personal rich signatures.

* ``GET /organization`` — any account member (needed for previews)
* ``PUT /organization`` — administrators only
* ``GET /personal``     — current member's own signature
* ``PUT /personal``     — current member's own signature
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.domains.email import signatures_service as svc
from app.domains.email.models import EmailSignature

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/email_signatures",
    tags=["email-signatures"],
)


class SignatureUpsert(BaseModel):
    signature_html: str | None = None
    signature_text: str | None = None
    signature_design: dict[str, Any] | None = None


def present_signature(
    row: EmailSignature | None, *, scope: str, fallback_text: str = ""
) -> dict[str, Any]:
    if row is None:
        return {
            "id": None,
            "scope": scope,
            "signature_html": "",
            "signature_text": "",
            "signature_design": None,
            "fallback_text": fallback_text,
            "created_at": None,
            "updated_at": None,
        }
    return {
        "id": row.id,
        "scope": scope,
        "signature_html": row.signature_html,
        "signature_text": row.signature_text,
        "signature_design": row.signature_design,
        "fallback_text": fallback_text,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/organization")
async def show_org_signature(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    row = await svc.get_org_signature(session, account_id=ctx.account.id)
    return present_signature(row, scope="organization")


@router.put("/organization")
async def update_org_signature(
    payload: SignatureUpsert,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    fields = payload.model_fields_set
    row = await svc.upsert_signature(
        session,
        account_id=ctx.account.id,
        user_id=None,
        signature_html=payload.signature_html if "signature_html" in fields else None,
        signature_text=payload.signature_text if "signature_text" in fields else None,
        signature_design=payload.signature_design if "signature_design" in fields else None,
        design_provided="signature_design" in fields,
    )
    return present_signature(row, scope="organization")


@router.get("/personal")
async def show_personal_signature(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    row = await svc.get_user_signature(session, account_id=ctx.account.id, user_id=ctx.user.id)
    return present_signature(
        row,
        scope="personal",
        fallback_text=(ctx.user.message_signature or ""),
    )


@router.put("/personal")
async def update_personal_signature(
    payload: SignatureUpsert,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    fields = payload.model_fields_set
    row = await svc.upsert_signature(
        session,
        account_id=ctx.account.id,
        user_id=ctx.user.id,
        signature_html=payload.signature_html if "signature_html" in fields else None,
        signature_text=payload.signature_text if "signature_text" in fields else None,
        signature_design=payload.signature_design if "signature_design" in fields else None,
        design_provided="signature_design" in fields,
    )
    return present_signature(
        row,
        scope="personal",
        fallback_text=(ctx.user.message_signature or ""),
    )


__all__ = ["present_signature", "router"]
