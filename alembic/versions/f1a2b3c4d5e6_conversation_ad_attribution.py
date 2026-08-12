"""conversation ad attribution (click-to-WhatsApp / click-to-Messenger)

Meta attaches a ``referral`` block to the first inbound message when the
person arrived from an ad. We denormalise the fields reports group by into
indexed columns and keep the untouched block in ``ad_referral`` so a payload
whose shape we did not anticipate is never lost.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations", sa.Column("ad_source", sa.String(), nullable=True)
    )
    op.add_column("conversations", sa.Column("ad_id", sa.String(), nullable=True))
    op.add_column(
        "conversations", sa.Column("ad_headline", sa.Text(), nullable=True)
    )
    op.add_column(
        "conversations", sa.Column("ad_click_id", sa.String(), nullable=True)
    )
    op.add_column(
        "conversations",
        sa.Column(
            "ad_referral",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("ad_captured_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "index_conversations_on_account_ad_created",
        "conversations",
        ["account_id", "ad_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "index_conversations_on_account_ad_created", table_name="conversations"
    )
    for col in (
        "ad_captured_at",
        "ad_referral",
        "ad_click_id",
        "ad_headline",
        "ad_id",
        "ad_source",
    ):
        op.drop_column("conversations", col)
