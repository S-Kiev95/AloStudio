"""Closing notes (F17).

When an agent resolves a conversation from the panel, they say why (a
category the account defines) and may add a note. The reports count
conversations by category. Resolving from automations, bulk actions or the
API asks nothing: only the panel's close button does.
"""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Boolean, Column, ForeignKey, Index, String, Text
from sqlmodel import Field

from app.core.base_model import TimestampMixin

CATEGORY_MAX = 60
CATEGORIES_MAX = 30
NOTE_MAX = 2000


class ClosingSettings(TimestampMixin, table=True):
    """Whether an account asks why its conversations close, and the choices."""

    __tablename__ = "closing_settings"

    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
        )
    )
    enabled: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # Closing from the panel needs a category.
    required: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # The categories, in order; None means the defaults.
    categories: list[str] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True), nullable=True)
    )


class ConversationClosing(TimestampMixin, table=True):
    """One time a conversation was closed with a reason or a note."""

    __tablename__ = "conversation_closings"
    __table_args__ = (
        Index("index_conversation_closings_on_account_created", "account_id", "created_at"),
        Index("index_conversation_closings_on_conversation", "conversation_id"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    conversation_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
        )
    )
    # The title as it was when chosen (a later rename keeps old reports).
    category: str | None = Field(default=None, sa_column=Column(String(CATEGORY_MAX), nullable=True))
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    user_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    # The private note it left in the conversation.
    message_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))


__all__ = [
    "CATEGORIES_MAX",
    "CATEGORY_MAX",
    "NOTE_MAX",
    "ClosingSettings",
    "ConversationClosing",
]
