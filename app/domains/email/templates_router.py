"""``/api/v1/accounts/{id}/email_templates`` — shared letterheads.

Admin-only, matching the rest of the inbox-settings surface: a template
is what every customer of the organisation receives.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.email import templates_service as svc
from app.domains.email.models import EmailTemplate
from app.domains.email.test_send import send_template_test
from app.domains.inboxes.models import CHANNEL_TYPE_EMAIL, EmailChannel, Inbox

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/email_templates",
    tags=["email-templates"],
)


class TemplateCreate(BaseModel):
    name: str
    template_html: str = ""
    template_design: dict[str, Any] | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    template_html: str | None = None
    template_design: dict[str, Any] | None = None


class TestSendRequest(BaseModel):
    """Which mailbox carries the test, and to whom."""

    inbox_id: int
    to: str


def present(row: EmailTemplate) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "template_html": row.template_html,
        "template_design": row.template_design,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def _find(
    session: AsyncSession, ctx: AccountContext, template_id: int
) -> EmailTemplate:
    assert ctx.account.id is not None
    row = await svc.get_template(
        session, account_id=ctx.account.id, template_id=template_id
    )
    if row is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return row


@router.get("")
async def index_templates(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    rows = await svc.list_templates(session, account_id=ctx.account.id)
    return {"payload": [present(r) for r in rows]}


@router.post("", status_code=status.HTTP_200_OK)
async def create_template(
    payload: TemplateCreate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    row = await svc.create_template(
        session,
        account_id=ctx.account.id,
        name=payload.name,
        template_html=payload.template_html,
        template_design=payload.template_design,
    )
    return present(row)


@router.get("/{template_id}")
async def show_template(
    template_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    return present(await _find(session, ctx, template_id))


@router.patch("/{template_id}")
async def update_template(
    template_id: Annotated[int, Path()],
    payload: TemplateUpdate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find(session, ctx, template_id)
    updates = payload.model_dump(exclude_unset=True)
    return present(await svc.update_template(session, template=row, updates=updates))


@router.delete("/{template_id}", status_code=status.HTTP_200_OK)
async def destroy_template(
    template_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find(session, ctx, template_id)
    await svc.delete_template(session, template=row)
    # Mailboxes that pointed at it keep working on their own HTML.
    return {"message": "La plantilla fue eliminada."}


@router.post("/{template_id}/test_send")
async def test_send_template(
    template_id: Annotated[int, Path()],
    payload: TestSendRequest,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mail this template, filled with sample content, to an address.

    Goes out through the chosen mailbox's own SMTP, so it also proves the
    transport that will carry the real replies.
    """
    row = await _find(session, ctx, template_id)
    assert ctx.account.id is not None

    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.id == payload.inbox_id,
                Inbox.account_id == ctx.account.id,
                Inbox.channel_type == CHANNEL_TYPE_EMAIL,
            )
        )
    ).first()
    if inbox is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    channel = await session.get(EmailChannel, inbox.channel_id)
    if channel is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )

    to = (payload.to or "").strip()
    if "@" not in to:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Poné una dirección de correo válida."},
        )

    result = await send_template_test(
        channel=channel, to_address=to, template_html=row.template_html
    )
    if not result.ok:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": result.error}
        )
    return {"message": f"Enviamos la prueba a {to}. Revisá esa casilla."}


__all__ = ["router"]
