"""Reusable email templates, owned by the account.

Until now a mailbox carried its own single ``template_html``: three
mailboxes meant three copies of the same letterhead, and an organisation
that wanted a different look for a welcome, a resolution notice and a
maintenance advisory had nowhere to put them.

A template lives on the account and a mailbox points at one. The
mailbox's own ``template_html`` stays as the fallback, so every mailbox
connected before this keeps rendering exactly as it did.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.core.base_model import TimestampMixin


class EmailTemplate(TimestampMixin, SQLModel, table=True):
    """One named letterhead an account can reuse across mailboxes."""

    __tablename__ = "email_templates"
    __table_args__ = (
        # Two templates called "Bienvenida" in one account is a picker
        # nobody can use. Scoped to the account, so tenants don't collide.
        UniqueConstraint("account_id", "name", name="uq_email_templates_account_name"),
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
    name: str = Field(sa_column=Column(String, nullable=False))

    # The authored markup. Must contain ``{{contenido}}`` — enforced on
    # save, because without it every reply goes out as an empty shell and
    # the send still succeeds.
    template_html: str = Field(
        default="", sa_column=Column(String, nullable=False, server_default="")
    )
    # What the visual designer produced ``template_html`` from, so it can
    # be reopened for editing instead of only re-generated.
    template_design: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )


__all__ = ["EmailTemplate"]
