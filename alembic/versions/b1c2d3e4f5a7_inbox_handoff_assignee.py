"""inboxes: default assignee for bot handoffs

Adds ``inboxes.handoff_assignee_id`` (nullable, FK to users, SET NULL when
the user is deleted). Null for every existing inbox: nothing changes until
an administrator picks someone.

Revision ID: b1c2d3e4f5a7
Revises: a0b1c2d3e4f6
Create Date: 2026-11-10 13:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1c2d3e4f5a7"
down_revision: str | None = "a0b1c2d3e4f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inboxes",
        sa.Column(
            "handoff_assignee_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id",
                name="fk_inboxes_handoff_assignee_id_users",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )
    op.create_index("index_inboxes_on_handoff_assignee_id", "inboxes", ["handoff_assignee_id"])


def downgrade() -> None:
    op.drop_index("index_inboxes_on_handoff_assignee_id", table_name="inboxes")
    op.drop_constraint("fk_inboxes_handoff_assignee_id_users", "inboxes", type_="foreignkey")
    op.drop_column("inboxes", "handoff_assignee_id")
