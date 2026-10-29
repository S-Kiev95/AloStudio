"""publishing: signatures and sets

Adds ``publishing_signatures`` (saved texts the composer adds to a
publication, one of them optionally on its own) and ``publication_sets``
(the composer saved under a name, to start publications from).

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
Create Date: 2026-10-29 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "1b2c3d4e5f6a"
down_revision: str | None = "0a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_id",
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
    ]


def upgrade() -> None:
    op.create_table(
        "publishing_signatures",
        *_common(),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("auto_add", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_publishing_signatures_account_id", "publishing_signatures", ["account_id"]
    )
    op.create_table(
        "publication_sets",
        *_common(),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index("ix_publication_sets_account_id", "publication_sets", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_publication_sets_account_id", table_name="publication_sets")
    op.drop_table("publication_sets")
    op.drop_index("ix_publishing_signatures_account_id", table_name="publishing_signatures")
    op.drop_table("publishing_signatures")
