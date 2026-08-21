"""settings the operator can change without SSH into the server

The Meta app credentials, webhook verify tokens and the public URL lived
only in ``.env.local``, so a deployment that started without them needed
a shell on the box to ever gain them. The point of the deployment story
is the opposite: install it empty, and fill settings in from the
dashboard as you obtain them.

Schema mirrors Chatwoot's ``installation_configs`` — name unique, the
value wrapped under a ``value`` key in JSONB, and a ``locked`` flag for
rows the dashboard must not offer. Wrapped rather than bare because
JSONB cannot hold a top-level null distinguishably from SQL NULL, and
"set to empty on purpose" has to differ from "never set": the first
overrides the environment, the second falls back to it.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installation_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "serialized_value",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "locked", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_installation_configs_name",
        "installation_configs",
        ["name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_installation_configs_name", table_name="installation_configs")
    op.drop_table("installation_configs")
