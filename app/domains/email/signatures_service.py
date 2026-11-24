"""Rich email signatures: organisation-wide and per-user CRUD and resolution.

Two scopes live in ``email_signatures``:
  * **Organisation** (``user_id IS NULL``): one per account, edited by
    administrators. Inserted via ``{{firma_organizacion}}`` or as the
    fallback for ``{{firma}}`` when the replying user has no signature.
  * **User** (``user_id == user.id``): one per user per account, edited by
    that user. Inserted via ``{{firma}}`` (and ``{{firma_agente}}``).

Fallback to legacy text:
  * If the user has no designed HTML signature (and no ``signature_text``),
    their existing plain-text ``users.message_signature`` is used, escaped
    exactly as before.
  * If the organisation has no designed HTML signature (and no
    ``signature_text``), the mailbox's ``channel_email.signature`` is used,
    escaped as before.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.email.models import EmailSignature
from app.domains.email.sanitize import sanitize_email_html
from app.domains.email.template import (
    plain_to_html,
    render_signature_variables,
    render_signature_variables_plain,
)

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLOCK_END_RE = re.compile(r"</(?:p|div|tr|li|h[1-6])\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_plain(html: str) -> str:
    """Best-effort plain text when a signature only has HTML and no text copy."""
    if not html:
        return ""
    text = _BR_RE.sub("\n", html)
    text = _BLOCK_END_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


@dataclass(slots=True)
class ResolvedSignatures:
    """Both HTML and plain-text signatures ready for ``render_template`` / ``render_plain``."""

    user_html: str = ""
    org_html: str = ""
    user_plain: str = ""
    org_plain: str = ""


async def get_org_signature(session: AsyncSession, *, account_id: int) -> EmailSignature | None:
    stmt = select(EmailSignature).where(
        EmailSignature.account_id == account_id,
        EmailSignature.user_id.is_(None),  # type: ignore[union-attr]
    )
    return (await session.exec(stmt)).first()


async def get_user_signature(
    session: AsyncSession, *, account_id: int, user_id: int
) -> EmailSignature | None:
    stmt = select(EmailSignature).where(
        EmailSignature.account_id == account_id,
        EmailSignature.user_id == user_id,
    )
    return (await session.exec(stmt)).first()


async def upsert_signature(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int | None,
    signature_html: str | None = None,
    signature_text: str | None = None,
    signature_design: dict[str, Any] | None = None,
    design_provided: bool = False,
) -> EmailSignature:
    """Create or update the organisation or user signature, sanitizing HTML."""
    row = (
        await get_org_signature(session, account_id=account_id)
        if user_id is None
        else await get_user_signature(session, account_id=account_id, user_id=user_id)
    )
    if row is None:
        row = EmailSignature(account_id=account_id, user_id=user_id)

    if signature_html is not None:
        row.signature_html = sanitize_email_html(signature_html)
        if not design_provided:
            # Hand-edited HTML without a canvas design forgets the stale design.
            row.signature_design = None
    if signature_text is not None:
        row.signature_text = str(signature_text).strip()
    if design_provided:
        row.signature_design = signature_design

    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


def _user_vars(user: Any | None) -> dict[str, str]:
    if user is None:
        return {"name": "", "job_title": "", "email": "", "phone": "", "avatar_url": ""}
    attrs = getattr(user, "custom_attributes", None) or {}
    phone = attrs.get("phone_number") if isinstance(attrs, dict) else ""
    name = (
        getattr(user, "available_name", None)
        or getattr(user, "display_name", None)
        or getattr(user, "name", None)
        or ""
    )
    return {
        "name": str(name),
        "job_title": str(getattr(user, "job_title", None) or ""),
        "email": str(getattr(user, "email", None) or ""),
        "phone": str(phone or ""),
        "avatar_url": str(getattr(user, "avatar_url", None) or ""),
    }


async def resolve_signatures(
    session: AsyncSession,
    *,
    account_id: int,
    user: Any | None = None,
    channel: Any | None = None,
) -> ResolvedSignatures:
    """Resolve user and organisation signatures for an outgoing reply.

    User signature precedence:
      1. ``email_signatures`` row for ``(account_id, user.id)`` — HTML if set,
         else its plain ``signature_text``.
      2. Legacy ``user.message_signature`` (escaped plain text).

    Organisation signature precedence:
      1. ``email_signatures`` row for ``(account_id, NULL)`` — HTML if set,
         else its plain ``signature_text``.
      2. Legacy ``channel.signature`` (escaped plain text).
    """
    vars_dict = _user_vars(user)
    plain_vars = {k: v for k, v in vars_dict.items() if k != "avatar_url"}

    user_id = getattr(user, "id", None)
    user_row = (
        await get_user_signature(session, account_id=account_id, user_id=user_id)
        if user_id is not None
        else None
    )
    org_row = await get_org_signature(session, account_id=account_id)

    # --- User signature ---
    user_html = ""
    user_plain = ""
    if user_row is not None and user_row.signature_html.strip():
        user_html = render_signature_variables(
            sanitize_email_html(user_row.signature_html), **vars_dict
        )
        user_plain = (
            render_signature_variables_plain(user_row.signature_text, **plain_vars)
            if user_row.signature_text.strip()
            else _html_to_plain(user_html)
        )
    elif user_row is not None and user_row.signature_text.strip():
        user_plain = render_signature_variables_plain(user_row.signature_text, **plain_vars)
        user_html = plain_to_html(user_plain)
    else:
        legacy_user = (getattr(user, "message_signature", None) or "").strip()
        if legacy_user:
            user_plain = legacy_user
            user_html = plain_to_html(legacy_user)

    # --- Organisation signature ---
    org_html = ""
    org_plain = ""
    if org_row is not None and org_row.signature_html.strip():
        org_html = render_signature_variables(
            sanitize_email_html(org_row.signature_html), **vars_dict
        )
        org_plain = (
            render_signature_variables_plain(org_row.signature_text, **plain_vars)
            if org_row.signature_text.strip()
            else _html_to_plain(org_html)
        )
    elif org_row is not None and org_row.signature_text.strip():
        org_plain = render_signature_variables_plain(org_row.signature_text, **plain_vars)
        org_html = plain_to_html(org_plain)
    else:
        legacy_channel = (getattr(channel, "signature", None) or "").strip()
        if legacy_channel:
            org_plain = legacy_channel
            org_html = plain_to_html(legacy_channel)

    return ResolvedSignatures(
        user_html=user_html,
        org_html=org_html,
        user_plain=user_plain,
        org_plain=org_plain,
    )


__all__ = [
    "ResolvedSignatures",
    "get_org_signature",
    "get_user_signature",
    "resolve_signatures",
    "upsert_signature",
]
