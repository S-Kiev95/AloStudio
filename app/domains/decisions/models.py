"""Decisions about conversations (F10).

A decisions service (TypeSafe's Jev today, a local Laya later: both answer
``POST /v1/systemone``) reads a conversation and picks, for each question the
account asks, one of a few options: intent, sentiment, urgency, team.

It runs in shadow first: decisions are stored and measured, nothing in the
conversation changes. People label conversations themselves, without seeing
the service's answer (:class:`HumanDecision`); that is the evaluation set and,
later, what Laya trains on. Jev's own answers never train another model: its
terms forbid distillation (Master Customer Agreement 2.3(b)).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin


class DecisionSettings(TimestampMixin, table=True):
    """What an account asks about its conversations, and whether it does."""

    __tablename__ = "decision_settings"

    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
        )
    )
    # Shadow mode: decide and store, change nothing.
    enabled: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # ``[{key, enabled, instructions, options: [{key, description}]}]``; None
    # means the defaults (:mod:`app.domains.decisions.questions`).
    questions: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True), nullable=True)
    )


class ConversationDecision(TimestampMixin, table=True):
    """One answer of the decisions service about one conversation."""

    __tablename__ = "conversation_decisions"
    __table_args__ = (
        Index("index_conversation_decisions_on_conversation", "conversation_id"),
        Index("index_conversation_decisions_on_account_question", "account_id", "question"),
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
    # The newest message the decision saw.
    message_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    question: str = Field(sa_column=Column(String(64), nullable=False))
    answer: str = Field(sa_column=Column(String(128), nullable=False))
    confidence: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    probabilities: dict[str, float] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True), nullable=True)
    )
    model: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))


class HumanDecision(TimestampMixin, table=True):
    """What a person says the answer is, without having seen the service's.
    The evaluation set, and Laya's training data."""

    __tablename__ = "conversation_human_decisions"
    __table_args__ = (
        UniqueConstraint("conversation_id", "question", name="uniq_human_decision_question"),
        Index("index_conversation_human_decisions_on_account", "account_id"),
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
    question: str = Field(sa_column=Column(String(64), nullable=False))
    answer: str = Field(sa_column=Column(String(128), nullable=False))
    user_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
