"""let a mailbox bring its own HTML for the whole reply

The signature and logo customise the footer of a fixed layout. Some
institutions need the layout itself — a header, their colours, a
structure the built-in card cannot express.

Empty means the built-in layout, so nothing changes for a mailbox nobody
customises. The column is authored markup on purpose, unlike ``signature``
which is escaped; what gets substituted into it is escaped instead, so the
author controls the layout while the agent's text cannot inject anything.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channel_email",
        sa.Column("template_html", sa.Text(), nullable=True, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("channel_email", "template_html")
