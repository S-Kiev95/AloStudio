"""phase4b: labels + conversation_labels

Adds the ``labels`` first-class table (account-scoped, with title +
color + sidebar metadata) and the ``conversation_labels`` join table
that replaces Chatwoot's polymorphic ``acts_as_taggable_on`` taggings.
See :class:`app.domains.labels.models.Label` and
:class:`app.domains.conversations.models.ConversationLabel` for the
design rationale.

Revision ID: d8e9f0a1b2c3
Revises: c7a8d1e3f4b9
Create Date: 2026-04-25 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | Sequence[str] | None = "c7a8d1e3f4b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # labels — Chatwoot's first-class label table
    # ------------------------------------------------------------------
    op.create_table(
        "labels",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "color",
            sa.String(),
            server_default="#1f93ff",
            nullable=False,
        ),
        sa.Column("show_on_sidebar", sa.Boolean(), nullable=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("index_labels_on_account_id", "labels", ["account_id"])
    op.create_index(
        "index_labels_on_title_and_account_id",
        "labels",
        ["title", "account_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # conversation_labels — direct (conversation, label) join.
    # Replaces ``acts_as_taggable_on`` taggings; see model docstring.
    # ------------------------------------------------------------------
    op.create_table(
        "conversation_labels",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("label_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["label_id"], ["labels.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_conversation_labels_on_conversation_id",
        "conversation_labels",
        ["conversation_id"],
    )
    op.create_index(
        "index_conversation_labels_on_label_id",
        "conversation_labels",
        ["label_id"],
    )
    op.create_index(
        "index_conversation_labels_on_conversation_and_label",
        "conversation_labels",
        ["conversation_id", "label_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "index_conversation_labels_on_conversation_and_label",
        table_name="conversation_labels",
    )
    op.drop_index(
        "index_conversation_labels_on_label_id",
        table_name="conversation_labels",
    )
    op.drop_index(
        "index_conversation_labels_on_conversation_id",
        table_name="conversation_labels",
    )
    op.drop_table("conversation_labels")

    op.drop_index(
        "index_labels_on_title_and_account_id", table_name="labels"
    )
    op.drop_index("index_labels_on_account_id", table_name="labels")
    op.drop_table("labels")
