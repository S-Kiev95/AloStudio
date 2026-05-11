"""phase6: csat_survey_responses

Adds the ``csat_survey_responses`` table backing
:class:`app.domains.csat.models.CsatSurveyResponse`.

Mirrors ``reference/chatwoot/db/schema.rb`` (table
``csat_survey_responses``, v4.13.0).

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-05-09 19:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "csat_survey_responses",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.BigInteger(),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            sa.BigInteger(),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("feedback_message", sa.Text(), nullable=True),
        sa.Column(
            "assigned_agent_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("csat_review_notes", sa.Text(), nullable=True),
        sa.Column(
            "review_notes_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "review_notes_updated_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "index_csat_survey_responses_on_account_id",
        "csat_survey_responses",
        ["account_id"],
    )
    op.create_index(
        "index_csat_survey_responses_on_assigned_agent_id",
        "csat_survey_responses",
        ["assigned_agent_id"],
    )
    op.create_index(
        "index_csat_survey_responses_on_contact_id",
        "csat_survey_responses",
        ["contact_id"],
    )
    op.create_index(
        "index_csat_survey_responses_on_conversation_id",
        "csat_survey_responses",
        ["conversation_id"],
    )
    op.create_index(
        "index_csat_survey_responses_on_review_notes_updated_by_id",
        "csat_survey_responses",
        ["review_notes_updated_by_id"],
    )
    op.create_index(
        "index_csat_survey_responses_on_message_id",
        "csat_survey_responses",
        ["message_id"],
        unique=True,
    )


def downgrade() -> None:
    for name in (
        "index_csat_survey_responses_on_message_id",
        "index_csat_survey_responses_on_review_notes_updated_by_id",
        "index_csat_survey_responses_on_conversation_id",
        "index_csat_survey_responses_on_contact_id",
        "index_csat_survey_responses_on_assigned_agent_id",
        "index_csat_survey_responses_on_account_id",
    ):
        op.drop_index(name, table_name="csat_survey_responses")
    op.drop_table("csat_survey_responses")
