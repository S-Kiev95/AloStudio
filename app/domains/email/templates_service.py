"""Shared and personal email templates: CRUD, resolution, and test send.

Two scopes live in ``email_templates``:
  * **Organisation** (``user_id IS NULL``): managed by administrators and
    assignable to email mailboxes (``channel_email.email_template_id``).
  * **Personal** (``user_id == user.id``): private to each member inside an
    account. A member may mark one personal template as ``is_default=True``
    so their outgoing replies use it ahead of the mailbox template.

Template resolution precedence on outgoing replies (:func:`resolve_html`):
  1. The replying user's personal default template (``is_default=True``), if
     present and non-empty.
  2. The mailbox's linked organisation template (``channel.email_template_id``),
     if present and non-empty.
  3. The mailbox's own ``channel.template_html``.
  4. Empty string — falls back to the built-in layout in :mod:`template`.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.email.models import EmailTemplate
from app.domains.email.sanitize import sanitize_email_html
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
    session: AsyncSession, *, account_id: int, user_id: int | None = None
) -> list[EmailTemplate]:
    """List organisation templates (``user_id=None``) or one user's personal ones."""
    stmt = select(EmailTemplate).where(EmailTemplate.account_id == account_id)
    if user_id is None:
        stmt = stmt.where(EmailTemplate.user_id.is_(None))  # type: ignore[union-attr]
    else:
        stmt = stmt.where(EmailTemplate.user_id == user_id)
    return list((await session.exec(stmt.order_by(EmailTemplate.name))).all())


async def get_template(
    session: AsyncSession,
    *,
    account_id: int,
    template_id: int,
    user_id: int | None = None,
) -> EmailTemplate | None:
    """Fetch one template enforcing both tenant (account) and owner scope."""
    row = await session.get(EmailTemplate, template_id)
    if row is None or row.account_id != account_id or row.user_id != user_id:
        return None
    return row


async def get_personal_default_template(
    session: AsyncSession, *, account_id: int, user_id: int
) -> EmailTemplate | None:
    stmt = select(EmailTemplate).where(
        EmailTemplate.account_id == account_id,
        EmailTemplate.user_id == user_id,
        EmailTemplate.is_default.is_(True),  # type: ignore[attr-defined]
    )
    return (await session.exec(stmt)).first()


async def resolve_html(
    session: AsyncSession,
    *,
    channel: Any,
    account_id: int | None = None,
    sender_user_id: int | None = None,
) -> str:
    """Resolve the template HTML for an outgoing reply.

    Precedence:
      1. Replying user's personal default template (``is_default=True``), if
         it has non-empty HTML.
      2. Mailbox's linked organisation template (``channel.email_template_id``),
         if it exists, is an organisation template, and has non-empty HTML.
      3. Mailbox's own ``channel.template_html``.
      4. ``""`` (built-in default layout).
    """
    acct_id = account_id or getattr(channel, "account_id", None)
    if acct_id is not None and sender_user_id is not None:
        personal = await get_personal_default_template(
            session, account_id=int(acct_id), user_id=int(sender_user_id)
        )
        if personal is not None and personal.template_html.strip():
            return personal.template_html

    template_id = getattr(channel, "email_template_id", None)
    if template_id:
        row = await session.get(EmailTemplate, template_id)
        if row is not None and row.user_id is None and row.template_html.strip():
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
    cleaned = sanitize_email_html(str(raw or ""))
    try:
        validate_template(cleaned)
    except TemplateError as exc:
        raise ChatwootHTTPException(status_code=422, detail={"message": str(exc)}) from exc
    return cleaned


async def _assert_name_free(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int | None,
    name: str,
    exclude_id: int | None,
) -> None:
    stmt = select(EmailTemplate).where(
        EmailTemplate.account_id == account_id,
        EmailTemplate.name == name,
    )
    if user_id is None:
        stmt = stmt.where(EmailTemplate.user_id.is_(None))  # type: ignore[union-attr]
    else:
        stmt = stmt.where(EmailTemplate.user_id == user_id)
    existing = (await session.exec(stmt)).first()
    if existing is not None and existing.id != exclude_id:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"Ya existe una plantilla llamada «{name}»."},
        )


async def _clear_personal_defaults(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int,
    exclude_id: int | None = None,
) -> None:
    stmt = (
        update(EmailTemplate)
        .where(
            EmailTemplate.account_id == account_id,  # type: ignore[arg-type]
            EmailTemplate.user_id == user_id,  # type: ignore[arg-type]
            EmailTemplate.is_default.is_(True),  # type: ignore[attr-defined]
        )
        .values(is_default=False)
    )
    if exclude_id is not None:
        stmt = stmt.where(EmailTemplate.id != exclude_id)  # type: ignore[arg-type]
    await session.exec(stmt)  # type: ignore[call-overload]


async def create_template(
    session: AsyncSession,
    *,
    account_id: int,
    name: str,
    template_html: str = "",
    template_design: dict[str, Any] | None = None,
    user_id: int | None = None,
    is_default: bool = False,
) -> EmailTemplate:
    clean = _clean_name(name)
    await _assert_name_free(
        session,
        account_id=account_id,
        user_id=user_id,
        name=clean,
        exclude_id=None,
    )
    make_default = bool(is_default) and user_id is not None
    if make_default and user_id is not None:
        await _clear_personal_defaults(session, account_id=account_id, user_id=user_id)
    row = EmailTemplate(
        account_id=account_id,
        user_id=user_id,
        name=clean,
        is_default=make_default,
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
            user_id=template.user_id,
            name=clean,
            exclude_id=template.id,
        )
        template.name = clean
    if "template_html" in updates:
        template.template_html = _validated_html(updates["template_html"])
    if "template_design" in updates:
        template.template_design = updates["template_design"]
    if "is_default" in updates and template.user_id is not None:
        want_default = bool(updates["is_default"])
        if want_default:
            await _clear_personal_defaults(
                session,
                account_id=template.account_id,
                user_id=template.user_id,
                exclude_id=template.id,
            )
        template.is_default = want_default
    session.add(template)
    await session.flush()
    await session.refresh(template)
    return template


async def delete_template(session: AsyncSession, *, template: EmailTemplate) -> None:
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
    user_signature_html: str | None = None,
    org_signature_html: str | None = None,
) -> str:
    """The template filled with sample content, exactly as a reply would
    be rendered."""
    rich = user_signature_html is not None or org_signature_html is not None
    return render_template(
        template=template_html,
        body=SAMPLE_BODY,
        signature=signature,
        logo_url=logo_url,
        agent_signature=SAMPLE_AGENT_SIGNATURE,
        user_signature_html=user_signature_html,
        org_signature_html=org_signature_html,
        append_signature_if_missing=rich,
    )


__all__ = [
    "SAMPLE_AGENT_SIGNATURE",
    "SAMPLE_BODY",
    "create_template",
    "delete_template",
    "get_personal_default_template",
    "get_template",
    "list_templates",
    "render_sample",
    "resolve_html",
    "update_template",
]
