"""One answer of AloStudio's AI to a customer (PLAN.agente-ia.md, 2b).

Every run leaves a row: what it answered (or proposed, in shadow mode), the
tools it used and how it ended. In shadow mode the row is the suggestion
the panel shows above the composer, and its final status says whether the
team sent it as is, edited it or discarded it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

MODE_SHADOW = "shadow"
MODE_LIVE = "live"
MODES = (MODE_SHADOW, MODE_LIVE)

# Shadow: waiting for the team, then sent as is, edited or discarded. A
# newer suggestion on the same conversation replaces it ("superseded").
STATUS_SUGGESTED = "suggested"
STATUS_SENT = "sent"
STATUS_EDITED = "edited"
STATUS_DISCARDED = "discarded"
STATUS_SUPERSEDED = "superseded"
# Live: answered the customer.
STATUS_ANSWERED = "answered"
# Either mode: handed (or would hand) the conversation to a person.
STATUS_HANDOFF = "handoff"
STATUS_FAILED = "failed"


class AiReply(TimestampMixin, table=True):
    __tablename__ = "ai_replies"
    __table_args__ = (
        Index("ix_ai_replies_conversation_id", "conversation_id"),
        Index("ix_ai_replies_account_id_created_at", "account_id", "created_at"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        ),
    )
    conversation_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
        ),
    )
    agent_bot_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("agent_bots.id", ondelete="SET NULL"), nullable=True
        ),
    )
    # The customer message it answers.
    message_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    mode: str = Field(sa_column=Column(String(16), nullable=False))
    status: str = Field(sa_column=Column(String(16), nullable=False))
    # What it says (or would say) to the customer.
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    # For the team when it hands off: what was talked about.
    summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    # The message that went out (live answer, or the team's send in shadow).
    sent_message_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    # Tools it called: [{"name", "arguments", "ok"}].
    steps: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
