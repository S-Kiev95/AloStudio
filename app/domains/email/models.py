"""Reusable email templates (organisation & personal) and rich signatures.

Organisation templates (``user_id IS NULL``) are managed by administrators and
can be linked to email mailboxes (``channel_email.email_template_id``).

Personal templates (``user_id IS NOT NULL``) belong to one member in one
account: only that member sees or edits them, and they may mark one as
``is_default=True`` so their own replies use it ahead of the mailbox template.

Rich signatures live in :class:`EmailSignature`: one organisation signature per
account (``user_id IS NULL``, edited by administrators) and one personal
signature per ``(account_id, user_id)``. When a user has no designed signature,
sending falls back to their plain-text ``users.message_signature``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.core.base_model import TimestampMixin


class EmailTemplate(TimestampMixin, SQLModel, table=True):
    """One named letterhead, owned by the account or by a single member."""

    __tablename__ = "email_templates"
    __table_args__ = (
        # Names stay unique within the organisation templates of an account...
        Index(
            "uq_email_templates_account_org_name",
            "account_id",
            "name",
            unique=True,
            postgresql_where=text("user_id IS NULL"),
        ),
        # ...and within each user's personal templates in that account.
        Index(
            "uq_email_templates_account_user_name",
            "account_id",
            "user_id",
            "name",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        # At most one personal default template per (account, user).
        Index(
            "uq_email_templates_user_default",
            "account_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL AND is_default = true"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    is_default: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )

    # The authored markup. Must contain ``{{contenido}}`` — enforced on
    # save, because without it every reply goes out as an empty shell and
    # the send still succeeds. Always sanitized server-side before saving.
    template_html: str = Field(
        default="", sa_column=Column(String, nullable=False, server_default="")
    )
    # What the visual designer produced ``template_html`` from, so it can
    # be reopened for editing instead of only re-generated.
    template_design: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )


class EmailSignature(TimestampMixin, SQLModel, table=True):
    """A rich email signature, owned by the organisation or by a user."""

    __tablename__ = "email_signatures"
    __table_args__ = (
        Index(
            "uq_email_signatures_org",
            "account_id",
            unique=True,
            postgresql_where=text("user_id IS NULL"),
        ),
        Index(
            "uq_email_signatures_user",
            "account_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )
    signature_html: str = Field(
        default="", sa_column=Column(String, nullable=False, server_default="")
    )
    signature_text: str = Field(
        default="", sa_column=Column(String, nullable=False, server_default="")
    )
    signature_design: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )


__all__ = ["EmailSignature", "EmailTemplate"]
