"""Who takes a conversation that is handed off (PLAN.agente-ia.md, 2a).

Meta's agent (Business Agent) or AloStudio's AI hand a conversation to the
team through ``bot_handoff``; these rules say to whom. The most specific
level wins:

  * the chat — a rule on the contact, for all their handoffs;
  * a label — the first rule, in ``position`` order, whose label the
    conversation carries;
  * the inbox — ``inboxes.handoff_assignee_id`` (its "Responsable por
    defecto", which also takes new conversations);
  * the account — one rule for everything else.

None of them leaves the conversation unassigned, and the whole inbox is
told. A rule names a person of the account or AloStudio's AI (``to_ai``);
one that can't be used (the person left the account, no AI agent) passes
to the next level.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Index, Integer, String, text
from sqlmodel import Field

from app.core.base_model import TimestampMixin

SCOPE_ACCOUNT = "account"
SCOPE_LABEL = "label"
SCOPE_CONTACT = "contact"
SCOPES = (SCOPE_ACCOUNT, SCOPE_LABEL, SCOPE_CONTACT)


class HandoffRule(TimestampMixin, table=True):
    __tablename__ = "handoff_rules"
    __table_args__ = (
        Index(
            "uniq_handoff_rules_account",
            "account_id",
            unique=True,
            postgresql_where=text("scope = 'account'"),
        ),
        Index(
            "uniq_handoff_rules_label",
            "account_id",
            "label_id",
            unique=True,
            postgresql_where=text("label_id IS NOT NULL"),
        ),
        Index(
            "uniq_handoff_rules_contact",
            "account_id",
            "contact_id",
            unique=True,
            postgresql_where=text("contact_id IS NOT NULL"),
        ),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    scope: str = Field(sa_column=Column(String(16), nullable=False))
    label_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("labels.id", ondelete="CASCADE"), nullable=True),
    )
    contact_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True),
    )
    # The person who takes it, or AloStudio's AI.
    user_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    to_ai: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # Label rules: the first one that matches wins.
    position: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )


__all__ = ["SCOPES", "SCOPE_ACCOUNT", "SCOPE_CONTACT", "SCOPE_LABEL", "HandoffRule"]
