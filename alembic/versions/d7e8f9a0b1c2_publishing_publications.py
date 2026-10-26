"""publishing: publications and publication targets

Adds the account-scoped ``publications`` table (content written and
scheduled once) and ``publication_targets`` (one row per channel it goes
out to, published by the matching network adapter).

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-10-26 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: str | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "publications",
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
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "media",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "scheduled_for", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "state", sa.String(), nullable=False, server_default="draft"
        ),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=True
        ),
        *_timestamps(),
    )
    op.create_index(
        "index_publications_on_account_id_and_scheduled_for",
        "publications",
        ["account_id", "scheduled_for"],
    )
    op.create_index(
        "index_publications_on_state_and_scheduled_for",
        "publications",
        ["state", "scheduled_for"],
    )

    op.create_table(
        "publication_targets",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "publication_id",
            sa.BigInteger(),
            sa.ForeignKey("publications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inbox_id",
            sa.BigInteger(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("network", sa.String(), nullable=False),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("content_override", sa.Text(), nullable=True),
        sa.Column(
            "state", sa.String(), nullable=False, server_default="pending"
        ),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("permalink", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        *_timestamps(),
        sa.UniqueConstraint(
            "publication_id",
            "inbox_id",
            name="uniq_publication_targets_publication_inbox",
        ),
    )
    op.create_index(
        "index_publication_targets_on_account_id_and_inbox_id",
        "publication_targets",
        ["account_id", "inbox_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "index_publication_targets_on_account_id_and_inbox_id",
        table_name="publication_targets",
    )
    op.drop_table("publication_targets")
    op.drop_index(
        "index_publications_on_state_and_scheduled_for",
        table_name="publications",
    )
    op.drop_index(
        "index_publications_on_account_id_and_scheduled_for",
        table_name="publications",
    )
    op.drop_table("publications")
