"""contacts: profile picture (F14)

Adds ``contacts.avatar_url`` (our copy of the picture in the object store)
and ``contacts.avatar_refreshed_at`` (last time Meta was asked for it, found
or not). Both null for every existing contact: the daily refresh picks up
the active Instagram and Messenger ones.

Revision ID: c2d3e4f5a6b8
Revises: b1c2d3e4f5a7
Create Date: 2026-11-12 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c2d3e4f5a6b8"
down_revision: str | None = "b1c2d3e4f5a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("avatar_url", sa.String(), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("avatar_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contacts", "avatar_refreshed_at")
    op.drop_column("contacts", "avatar_url")
