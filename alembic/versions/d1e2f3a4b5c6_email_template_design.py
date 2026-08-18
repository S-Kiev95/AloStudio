"""remember the settings a visual template was built from

The HTML editor works for someone who writes HTML. For everyone else the
designer produces the same ``template_html`` from a handful of controls —
but reopening it needs those controls back, and parsing them out of the
generated markup would be guesswork that breaks the moment anyone edits
it.

Null means the HTML no longer corresponds to any set of controls, either
because it was written by hand or edited after being generated. The
designer refuses to silently overwrite that.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channel_email",
        sa.Column("template_design", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channel_email", "template_design")
