"""``/api/v1/accounts/{id}/email_templates`` — organisation & personal letterheads.

Two scopes:
  * **Organisation** (``/email_templates``, ``/email_templates/{id}``):
    admin-only, assignable to mailboxes.
  * **Personal** (``/email_templates/personal``, ``/email_templates/personal/{id}``):
    any account member manages their own private templates and can mark one
    as ``is_default=True`` for their outgoing replies.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import media_ai
from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.email import ai_design
from app.domains.email import signatures_service as sig_svc
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
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = None
    template_html: str | None = None
    template_design: dict[str, Any] | None = None
    is_default: bool | None = None


class TestSendRequest(BaseModel):
    """Which mailbox carries the test, and to whom."""

    inbox_id: int
    to: str


class GenerateDesignRequest(BaseModel):
    prompt: str = ""
    image: str | None = None
    kind: Literal["template", "signature"] = "template"


def present(row: EmailTemplate) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "scope": "personal" if row.user_id is not None else "organization",
        "user_id": row.user_id,
        "is_default": bool(row.is_default),
        "template_html": row.template_html,
        "template_design": row.template_design,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def _find(
    session: AsyncSession,
    ctx: AccountContext,
    template_id: int,
    *,
    user_id: int | None,
) -> EmailTemplate:
    assert ctx.account.id is not None
    row = await svc.get_template(
        session,
        account_id=ctx.account.id,
        template_id=template_id,
        user_id=user_id,
    )
    if row is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return row


async def _run_test_send(
    session: AsyncSession,
    ctx: AccountContext,
    row: EmailTemplate,
    payload: TestSendRequest,
) -> dict[str, Any]:
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

    sigs = await sig_svc.resolve_signatures(
        session,
        account_id=ctx.account.id,
        user=ctx.user,
        channel=channel,
    )
    result = await send_template_test(
        channel=channel,
        to_address=to,
        template_html=row.template_html,
        user_signature_html=sigs.user_html or None,
        org_signature_html=sigs.org_html or None,
        user_signature_plain=sigs.user_plain or None,
        org_signature_plain=sigs.org_plain or None,
    )
    if not result.ok:
        raise ChatwootHTTPException(status_code=422, detail={"message": result.error})
    return {"message": f"Enviamos la prueba a {to}. Revisá esa casilla."}


# ---------------------------------------------------------------------------
# AI design generation (any account member — never auto-saves)
# Registered before ``/{template_id}`` so ``/generate`` matches literally.
# ---------------------------------------------------------------------------
@router.get("/ai_status")
async def email_ai_status(
    ctx: Annotated[AccountContext, Depends(account_context)],
) -> dict[str, Any]:
    return {
        "enabled": ai_design.ai_available(ctx.account),
        "media": media_ai.available(),
    }


@router.post("/generate")
async def generate_template_or_signature(
    payload: GenerateDesignRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    try:
        result = await ai_design.generate_email_design(
            session,
            account=ctx.account,
            prompt=payload.prompt,
            kind=payload.kind,
            image=payload.image,
        )
    except ai_design.EmailAiError as exc:
        raise ChatwootHTTPException(
            status_code=exc.status_code,
            detail={"message": exc.message, "code": f"email_ai.{exc.code}"},
        ) from exc
    return {
        "html": result.html,
        "notes": result.notes,
        "mode": result.mode,
        "seen": result.seen,
    }


# ---------------------------------------------------------------------------
# Personal templates (any account member — private to ctx.user)
# Registered before ``/{template_id}`` so ``/personal`` matches literally.
# ---------------------------------------------------------------------------
@router.get("/personal")
async def index_personal_templates(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    rows = await svc.list_templates(session, account_id=ctx.account.id, user_id=ctx.user.id)
    return {"payload": [present(r) for r in rows]}


@router.post("/personal", status_code=status.HTTP_200_OK)
async def create_personal_template(
    payload: TemplateCreate,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None and ctx.user.id is not None
    row = await svc.create_template(
        session,
        account_id=ctx.account.id,
        user_id=ctx.user.id,
        name=payload.name,
        template_html=payload.template_html,
        template_design=payload.template_design,
        is_default=payload.is_default,
    )
    return present(row)


@router.get("/personal/{template_id}")
async def show_personal_template(
    template_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.user.id is not None
    return present(await _find(session, ctx, template_id, user_id=ctx.user.id))


@router.patch("/personal/{template_id}")
async def update_personal_template(
    template_id: Annotated[int, Path()],
    payload: TemplateUpdate,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.user.id is not None
    row = await _find(session, ctx, template_id, user_id=ctx.user.id)
    updates = payload.model_dump(exclude_unset=True)
    return present(await svc.update_template(session, template=row, updates=updates))


@router.delete("/personal/{template_id}", status_code=status.HTTP_200_OK)
async def destroy_personal_template(
    template_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.user.id is not None
    row = await _find(session, ctx, template_id, user_id=ctx.user.id)
    await svc.delete_template(session, template=row)
    return {"message": "La plantilla fue eliminada."}


@router.post("/personal/{template_id}/test_send")
async def test_send_personal_template(
    template_id: Annotated[int, Path()],
    payload: TestSendRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.user.id is not None
    row = await _find(session, ctx, template_id, user_id=ctx.user.id)
    return await _run_test_send(session, ctx, row, payload)


# ---------------------------------------------------------------------------
# Organisation templates (admin-only)
# ---------------------------------------------------------------------------
@router.get("")
async def index_templates(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    rows = await svc.list_templates(session, account_id=ctx.account.id, user_id=None)
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
        user_id=None,
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
    return present(await _find(session, ctx, template_id, user_id=None))


@router.patch("/{template_id}")
async def update_template(
    template_id: Annotated[int, Path()],
    payload: TemplateUpdate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find(session, ctx, template_id, user_id=None)
    updates = payload.model_dump(exclude_unset=True)
    updates.pop("is_default", None)
    return present(await svc.update_template(session, template=row, updates=updates))


@router.delete("/{template_id}", status_code=status.HTTP_200_OK)
async def destroy_template(
    template_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find(session, ctx, template_id, user_id=None)
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
    row = await _find(session, ctx, template_id, user_id=None)
    return await _run_test_send(session, ctx, row, payload)


__all__ = ["router"]
