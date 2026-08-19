"""only ingest mail that arrived after the mailbox was connected

SEARCH UNSEEN answers with a mailbox's whole unread backlog. Connecting a
real Gmail account to staging turned 114 newsletters into 114
conversations in three minutes; on a desk that has been running for years
it is thousands, and every one is something a person has to close.

Null means no bound, which is what every mailbox connected before this
had — changing them retroactively would be guessing at a date nobody
recorded. It is set going forward when IMAP is switched on.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channel_email",
        sa.Column("imap_fetch_since", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channel_email", "imap_fetch_since")
