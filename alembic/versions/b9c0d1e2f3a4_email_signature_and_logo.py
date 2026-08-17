"""give each mailbox a signature and a logo

Replies went out as bare plain text with no indication of who sent them.
Both fields hang off the mailbox rather than the account: the identity of
an outgoing email already lives there — the address it comes from, the
server it goes through — and support@ and sales@ commonly sign
differently.

Empty by default, and an empty signature renders nothing, so a mailbox
nobody configures keeps sending exactly what it sent before.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channel_email",
        sa.Column("signature", sa.Text(), nullable=True, server_default=""),
    )
    op.add_column(
        "channel_email",
        sa.Column("logo_url", sa.String(), nullable=True, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("channel_email", "logo_url")
    op.drop_column("channel_email", "signature")
