"""user avatar_url

Adds ``users.avatar_url`` — the resolved URL of an uploaded avatar image
(our MinIO/S3 direct-upload pipeline). Chatwoot models this as an
ActiveStorage attachment; we store the URL string directly.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-07-04 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6b7c8d9e0f1"
down_revision: str | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
