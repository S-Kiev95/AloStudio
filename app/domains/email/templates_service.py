"""Shared email templates: CRUD, resolution, and the test send.

The test send is not a nicety. Email HTML breaks where you cannot see
it — Outlook renders with Word's engine, Gmail clips a message past
102 KB, and most clients block images until the reader allows them. A
preview in the dashboard is a browser rendering, which is the one
environment the message will never be read in.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.email.models import EmailTemplate
from app.domains.email.template import TemplateError, render_template, validate_template

log = logging.getLogger(__name__)

# What the test send fills the placeholders with. Long enough to show
# wrapping, short enough to read at a glance.
SAMPLE_BODY = (
    "Hola, gracias por escribirnos.\n\n"
    "Este es un envío de prueba de la plantilla: sirve para verla como la "
    "va a ver quien reciba el correo, en su propio cliente y no en una "
    "vista previa del navegador.\n\n"
    "Si la cabecera, los colores y el logo se ven como esperabas, la "
    "plantilla está lista."
)
SAMPLE_AGENT_SIGNATURE = "Ana Pérez\nAtención al cliente"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
async def list_templates(
    session: AsyncSession, *, account_id: int
) -> list[EmailTemplate]:
    return list(
        (
            await session.exec(
                select(EmailTemplate)
                .where(EmailTemplate.account_id == account_id)
                .order_by(EmailTemplate.name)
            )
        ).all()
    )


async def get_template(
    session: AsyncSession, *, account_id: int, template_id: int
) -> EmailTemplate | None:
    row = await session.get(EmailTemplate, template_id)
    # The account check is the tenant boundary — never trust the path id
    # alone to belong to the caller.
    if row is None or row.account_id != account_id:
        return None
    return row


async def resolve_html(
    session: AsyncSession, *, channel: Any
) -> str:
    """The markup a mailbox should render with.

    A linked shared template wins; otherwise the mailbox's own
    ``template_html``, which is what every mailbox had before shared
    templates existed. A link pointing at a deleted row resolves to the
    fallback rather than to nothing.
    """
    template_id = getattr(channel, "email_template_id", None)
    if template_id:
        row = await session.get(EmailTemplate, template_id)
        if row is not None and row.template_html.strip():
            return row.template_html
    return getattr(channel, "template_html", "") or ""


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def _clean_name(raw: Any) -> str:
    name = str(raw or "").strip()
    if not name:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "La plantilla necesita un nombre."},
        )
    if len(name) > 120:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "El nombre no puede pasar de 120 caracteres."},
        )
    return name


def _validated_html(raw: Any) -> str:
    html = str(raw or "")
    try:
        validate_template(html)
    except TemplateError as exc:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": str(exc)}
        ) from exc
    return html


async def _assert_name_free(
    session: AsyncSession, *, account_id: int, name: str, exclude_id: int | None
) -> None:
    stmt = select(EmailTemplate).where(
        EmailTemplate.account_id == account_id, EmailTemplate.name == name
    )
    existing = (await session.exec(stmt)).first()
    if existing is not None and existing.id != exclude_id:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"Ya existe una plantilla llamada «{name}»."},
        )


async def create_template(
    session: AsyncSession,
    *,
    account_id: int,
    name: str,
    template_html: str = "",
    template_design: dict[str, Any] | None = None,
) -> EmailTemplate:
    clean = _clean_name(name)
    await _assert_name_free(
        session, account_id=account_id, name=clean, exclude_id=None
    )
    row = EmailTemplate(
        account_id=account_id,
        name=clean,
        template_html=_validated_html(template_html),
        template_design=template_design,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def update_template(
    session: AsyncSession,
    *,
    template: EmailTemplate,
    updates: dict[str, Any],
) -> EmailTemplate:
    if "name" in updates:
        clean = _clean_name(updates["name"])
        await _assert_name_free(
            session,
            account_id=template.account_id,
            name=clean,
            exclude_id=template.id,
        )
        template.name = clean
    if "template_html" in updates:
        template.template_html = _validated_html(updates["template_html"])
    if "template_design" in updates:
        template.template_design = updates["template_design"]
    session.add(template)
    await session.flush()
    await session.refresh(template)
    return template


async def delete_template(
    session: AsyncSession, *, template: EmailTemplate
) -> None:
    """Remove it. Mailboxes pointing at it fall back to their own HTML —
    the FK is ON DELETE SET NULL, so none of them stops working."""
    await session.delete(template)
    await session.flush()


# ---------------------------------------------------------------------------
# Test send
# ---------------------------------------------------------------------------
def render_sample(
    *,
    template_html: str,
    signature: str = "",
    logo_url: str = "",
) -> str:
    """The template filled with sample content, exactly as a reply would
    be rendered."""
    return render_template(
        template=template_html,
        body=SAMPLE_BODY,
        signature=signature,
        logo_url=logo_url,
        agent_signature=SAMPLE_AGENT_SIGNATURE,
    )


__all__ = [
    "SAMPLE_AGENT_SIGNATURE",
    "SAMPLE_BODY",
    "create_template",
    "delete_template",
    "get_template",
    "list_templates",
    "render_sample",
    "resolve_html",
    "update_template",
]
