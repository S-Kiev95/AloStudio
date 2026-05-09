"""Macro — playbook of canned actions for one-click application.

Ported from:
  reference/chatwoot/app/models/macro.rb
  reference/chatwoot/db/schema.rb (``macros`` table, v4.13.0)

A Macro is a named ordered list of actions an agent can apply to one
or more conversations from the dashboard. Visibility controls who
can see the macro:

  * ``personal`` (0, default) — only the creator + admins.
  * ``global`` (1)            — everyone in the account.

The ``actions`` JSONB column stores an array of
``{action_name, action_params}`` dicts. ``action_name`` must be in
:data:`MACRO_ALLOWED_ACTIONS`. Validation runs at the service layer
(``json_actions_format`` in Rails).

The ``files`` ActiveStorage attachment from Chatwoot (used by the
``send_attachment`` action) defers to Phase 10 alongside the rest of
the MinIO+ActiveStorage equivalent — for 6.2 the action_name is
accepted but the executor short-circuits.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# Mirrors ``Macro::ACTIONS_ATTRS``. Order matters for parity with
# Chatwoot's docs — keep it aligned with the Ruby array.
MACRO_ALLOWED_ACTIONS: tuple[str, ...] = (
    "send_message",
    "add_label",
    "assign_team",
    "assign_agent",
    "mute_conversation",
    "change_status",
    "remove_label",
    "remove_assigned_agent",
    "remove_assigned_team",
    "resolve_conversation",
    "snooze_conversation",
    "change_priority",
    "send_email_transcript",
    "send_attachment",
    "add_private_note",
    "send_webhook_event",
)

# enum visibility: { personal: 0, global: 1 }
MACRO_VISIBILITY_PERSONAL = 0
MACRO_VISIBILITY_GLOBAL = 1


def macro_visibility_from_str(s: str | None) -> int:
    """Coerce the Rails string enum to the int we store on the row."""
    if s is None or s == "personal":
        return MACRO_VISIBILITY_PERSONAL
    if s == "global":
        return MACRO_VISIBILITY_GLOBAL
    raise ValueError(f"unknown visibility: {s!r}")


def macro_visibility_to_str(v: int | None) -> str:
    """Inverse of :func:`macro_visibility_from_str` for wire output."""
    if v == MACRO_VISIBILITY_GLOBAL:
        return "global"
    return "personal"


class Macro(TimestampMixin, table=True):
    """A reusable bundle of conversation actions, owned by one Account."""

    __tablename__ = "macros"
    __table_args__ = (
        Index("index_macros_on_account_id", "account_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    visibility: int = Field(
        default=MACRO_VISIBILITY_PERSONAL,
        sa_column=Column(
            Integer,
            nullable=False,
            server_default=str(MACRO_VISIBILITY_PERSONAL),
        ),
    )
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    updated_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    actions: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )


__all__ = [
    "MACRO_ALLOWED_ACTIONS",
    "MACRO_VISIBILITY_GLOBAL",
    "MACRO_VISIBILITY_PERSONAL",
    "Macro",
    "macro_visibility_from_str",
    "macro_visibility_to_str",
]
