"""CsatSurveyResponse — customer satisfaction rating submitted by a
contact in response to an ``input_csat`` template message.

Ported from:
  reference/chatwoot/app/models/csat_survey_response.rb
  reference/chatwoot/db/schema.rb (``csat_survey_responses`` table)

One survey response per ``input_csat`` message (``message_id`` is
UNIQUE). The contact submits via the public widget endpoint
``PUT /public/api/v1/csat_survey/{conversation_uuid}`` — see
:mod:`app.domains.csat.public_router`.

Rating is a 1–5 integer (Chatwoot's emoji + numeric scales both
collapse to this range). ``feedback_message`` is the optional
free-text comment, ``csat_review_notes`` is the agent's annotation
(distinct from the submitter's text).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin


class CsatSurveyResponse(TimestampMixin, table=True):
    """A single contact-submitted CSAT rating."""

    __tablename__ = "csat_survey_responses"
    __table_args__ = (
        Index(
            "index_csat_survey_responses_on_account_id", "account_id"
        ),
        Index(
            "index_csat_survey_responses_on_assigned_agent_id",
            "assigned_agent_id",
        ),
        Index(
            "index_csat_survey_responses_on_contact_id", "contact_id"
        ),
        Index(
            "index_csat_survey_responses_on_conversation_id",
            "conversation_id",
        ),
        Index(
            "index_csat_survey_responses_on_review_notes_updated_by_id",
            "review_notes_updated_by_id",
        ),
        UniqueConstraint(
            "message_id",
            name="index_csat_survey_responses_on_message_id",
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
    conversation_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    message_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    contact_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    rating: int = Field(sa_column=Column(Integer, nullable=False))
    feedback_message: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    assigned_agent_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    csat_review_notes: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    review_notes_updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    review_notes_updated_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


CSAT_VALID_RATINGS: tuple[int, ...] = (1, 2, 3, 4, 5)

# Chatwoot's controller rejects updates beyond 14 days from message
# creation. Mirror the threshold here as the single source of truth.
CSAT_LOCK_DAYS = 14


__all__ = [
    "CSAT_LOCK_DAYS",
    "CSAT_VALID_RATINGS",
    "CsatSurveyResponse",
]
