"""portal logo

Adds ``portals.logo`` — the resolved URL of an uploaded portal logo image
(our MinIO/S3 direct-upload pipeline). Chatwoot models this as an
ActiveStorage attachment; we store the URL string directly.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-07-04 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portals",
        sa.Column("logo", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portals", "logo")
