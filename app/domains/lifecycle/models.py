"""Contact lifecycle (F17).

Each account lists its stages (``stage``: the way to a sale; ``lost``: where
people drop out). A contact stands in at most one; the first message of a
contact who has none puts them in the default stage. Every change is kept,
for the reports and so the panel can say who moved whom.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Index, String
from sqlmodel import Field

from app.core.base_model import TimestampMixin

KIND_STAGE = "stage"
KIND_LOST = "lost"
STAGES_MAX = 20
NAME_MAX = 40
DESCRIPTION_MAX = 160
EMOJI_MAX = 8
KEY_MAX = 40


class LifecycleSettings(TimestampMixin, table=True):
    """Whether an account uses stages, and which."""

    __tablename__ = "lifecycle_settings"

    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
        )
    )
    enabled: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # ``[{key, name, emoji, description, kind, default}]`` in order; None
    # means the defaults.
    stages: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True), nullable=True)
    )


class ContactLifecycle(TimestampMixin, table=True):
    """The stage a contact stands in now."""

    __tablename__ = "contact_lifecycles"
    __table_args__ = (Index("index_contact_lifecycles_on_account_stage", "account_id", "stage_key"),)

    contact_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True
        )
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    stage_key: str = Field(sa_column=Column(String(KEY_MAX), nullable=False))
    changed_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    changed_by_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )


class LifecycleChange(TimestampMixin, table=True):
    """One move of a contact between stages (``None``: no stage)."""

    __tablename__ = "contact_lifecycle_changes"
    __table_args__ = (
        Index("index_contact_lifecycle_changes_on_account_created", "account_id", "created_at"),
        Index("index_contact_lifecycle_changes_on_contact", "contact_id"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    contact_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
        )
    )
    from_key: str | None = Field(default=None, sa_column=Column(String(KEY_MAX), nullable=True))
    to_key: str | None = Field(default=None, sa_column=Column(String(KEY_MAX), nullable=True))
    user_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )


__all__ = [
    "DESCRIPTION_MAX",
    "EMOJI_MAX",
    "KEY_MAX",
    "KIND_LOST",
    "KIND_STAGE",
    "NAME_MAX",
    "STAGES_MAX",
    "ContactLifecycle",
    "LifecycleChange",
    "LifecycleSettings",
]
