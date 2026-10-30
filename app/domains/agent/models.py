"""Agent chat: a user's conversations with the AI that drafts, schedules
and reviews publications through the publishing MCP tools.

An :class:`AgentThread` belongs to one user in one account (chats are not
shared). Its :class:`AgentMessage` rows are the model's chat history as
OpenAI takes it: ``user`` and ``assistant`` messages, and one ``tool`` row
per tool call with its result. A tool call that writes (create or cancel a
publication) stays ``pending`` until the user confirms or rejects it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

AGENT_ROLE_USER = "user"
AGENT_ROLE_ASSISTANT = "assistant"
AGENT_ROLE_TOOL = "tool"

TOOL_STATUS_PENDING = "pending"
TOOL_STATUS_DONE = "done"
TOOL_STATUS_ERROR = "error"
# A proposed write that failed its trial run: it went back to the model,
# the user never saw it as a proposal.
TOOL_STATUS_INVALID = "invalid"
TOOL_STATUS_REJECTED = "rejected"


class AgentThread(TimestampMixin, table=True):
    """One chat. ``updated_at`` moves with every turn (newest chats first)."""

    __tablename__ = "agent_threads"
    __table_args__ = (
        Index("ix_agent_threads_account_id_user_id", "account_id", "user_id"),
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
    user_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    title: str = Field(sa_column=Column(String, nullable=False))
    # The browser's IANA zone from the last message, so "tomorrow at 10"
    # keeps meaning the same after a confirmation (which carries no body).
    timezone: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    # Set while a turn runs: a second request on the same chat gets a 409
    # instead of interleaving with it. A crashed turn frees it after a while.
    running_since: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class AgentMessage(TimestampMixin, table=True):
    """A message of the chat history, oldest first by ``id``."""

    __tablename__ = "agent_messages"
    __table_args__ = (Index("ix_agent_messages_thread_id", "thread_id"),)

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    thread_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("agent_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    role: str = Field(sa_column=Column(String, nullable=False))
    # user / assistant text, or a tool row's JSON result.
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    # assistant rows: the tool calls exactly as the model returned them.
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    # tool rows: which call this answers, and what it ran with.
    tool_call_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    tool_name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    tool_arguments: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    status: str | None = Field(default=None, sa_column=Column(String, nullable=True))
