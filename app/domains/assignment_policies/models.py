"""AssignmentPolicy — per-account auto-assignment configuration.

Ported from:
  reference/chatwoot/app/models/assignment_policy.rb
  reference/chatwoot/app/models/inbox_assignment_policy.rb
  reference/chatwoot/db/schema.rb (v4.13.0)

A policy names an assignment strategy (round-robin, in OSS) plus the
conversation-pickup order and a fair-distribution cap (at most
``fair_distribution_limit`` conversations assigned per agent within
``fair_distribution_window`` seconds). An inbox links to at most one policy
via :class:`InboxAssignmentPolicy`.

This ships the CRUD + inbox-linking surface (stage 1). Wiring the auto-
assignment runtime to *honour* the fair-distribution cap is a follow-up.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# enum assignment_order: { round_robin: 0 } (OSS)
ASSIGNMENT_ORDER_ROUND_ROBIN = 0
# enum conversation_priority: { earliest_created: 0, longest_waiting: 1 }
CONVERSATION_PRIORITY_EARLIEST_CREATED = 0
CONVERSATION_PRIORITY_LONGEST_WAITING = 1

_ORDER_INT_TO_STR: dict[int, str] = {ASSIGNMENT_ORDER_ROUND_ROBIN: "round_robin"}
_ORDER_STR_TO_INT = {v: k for k, v in _ORDER_INT_TO_STR.items()}
_PRIORITY_INT_TO_STR: dict[int, str] = {
    CONVERSATION_PRIORITY_EARLIEST_CREATED: "earliest_created",
    CONVERSATION_PRIORITY_LONGEST_WAITING: "longest_waiting",
}
_PRIORITY_STR_TO_INT = {v: k for k, v in _PRIORITY_INT_TO_STR.items()}


def assignment_order_from_str(s: str | None) -> int:
    if s is None:
        return ASSIGNMENT_ORDER_ROUND_ROBIN
    if s not in _ORDER_STR_TO_INT:
        raise ValueError(f"unknown assignment_order: {s!r}")
    return _ORDER_STR_TO_INT[s]


def assignment_order_to_str(v: int | None) -> str:
    return _ORDER_INT_TO_STR.get(v or 0, "round_robin")


def conversation_priority_from_str(s: str | None) -> int:
    if s is None:
        return CONVERSATION_PRIORITY_EARLIEST_CREATED
    if s not in _PRIORITY_STR_TO_INT:
        raise ValueError(f"unknown conversation_priority: {s!r}")
    return _PRIORITY_STR_TO_INT[s]


def conversation_priority_to_str(v: int | None) -> str:
    return _PRIORITY_INT_TO_STR.get(v or 0, "earliest_created")


class AssignmentPolicy(TimestampMixin, table=True):
    """A named auto-assignment strategy owned by one account."""

    __tablename__ = "assignment_policies"
    __table_args__ = (
        Index("index_assignment_policies_on_account_id", "account_id"),
        Index("index_assignment_policies_on_enabled", "enabled"),
        UniqueConstraint(
            "account_id",
            "name",
            name="index_assignment_policies_on_account_id_and_name",
        ),
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
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    assignment_order: int = Field(
        default=ASSIGNMENT_ORDER_ROUND_ROBIN,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    conversation_priority: int = Field(
        default=CONVERSATION_PRIORITY_EARLIEST_CREATED,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    fair_distribution_limit: int = Field(
        default=100,
        sa_column=Column(Integer, nullable=False, server_default="100"),
    )
    fair_distribution_window: int = Field(
        default=3600,
        sa_column=Column(Integer, nullable=False, server_default="3600"),
    )


class InboxAssignmentPolicy(TimestampMixin, table=True):
    """One-to-one link: an inbox uses (at most) one assignment policy."""

    __tablename__ = "inbox_assignment_policies"
    __table_args__ = (
        Index(
            "index_inbox_assignment_policies_on_assignment_policy_id",
            "assignment_policy_id",
        ),
        UniqueConstraint(
            "inbox_id", name="index_inbox_assignment_policies_on_inbox_id"
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    inbox_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    assignment_policy_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("assignment_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )


__all__ = [
    "ASSIGNMENT_ORDER_ROUND_ROBIN",
    "CONVERSATION_PRIORITY_EARLIEST_CREATED",
    "CONVERSATION_PRIORITY_LONGEST_WAITING",
    "AssignmentPolicy",
    "InboxAssignmentPolicy",
    "assignment_order_from_str",
    "assignment_order_to_str",
    "conversation_priority_from_str",
    "conversation_priority_to_str",
]
