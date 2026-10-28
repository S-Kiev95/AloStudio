"""publishing: channels as their own table

Adds ``publishing_channels`` (an account on a social network the account
publishes to; Instagram and Facebook Pages keep pointing at their inbox) and
moves ``publication_targets`` and ``channel_metric_snapshots`` from
``inbox_id`` to ``channel_id``. Existing rows get one channel per inbox they
used, so nothing is lost; the downgrade maps them back and drops rows of
channels without an inbox.

Revision ID: 0a1b2c3d4e5f
Revises: f9a0b1c2d3e4
Create Date: 2026-10-28 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0a1b2c3d4e5f"
down_revision: str | None = "f9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# One channel per inbox already used by a target or a snapshot, named
# after the inbox.
_BACKFILL_CHANNELS = """
INSERT INTO publishing_channels (account_id, network, name, inbox_id)
SELECT DISTINCT ON (used.inbox_id) used.account_id, used.network, inboxes.name, used.inbox_id
FROM (
    SELECT account_id, network, inbox_id FROM publication_targets
    UNION ALL
    SELECT account_id, network, inbox_id FROM channel_metric_snapshots
) AS used
JOIN inboxes ON inboxes.id = used.inbox_id
ORDER BY used.inbox_id
"""


def upgrade() -> None:
    op.create_table(
        "publishing_channels",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("network", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column(
            "inbox_id",
            sa.BigInteger(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "credentials",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("inbox_id", name="uniq_publishing_channels_inbox"),
    )
    op.create_index(
        "ix_publishing_channels_account_id", "publishing_channels", ["account_id"]
    )
    op.create_index(
        "uniq_publishing_channels_account_network_external",
        "publishing_channels",
        ["account_id", "network", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.execute(_BACKFILL_CHANNELS)

    # publication_targets: inbox_id -> channel_id
    op.add_column(
        "publication_targets", sa.Column("channel_id", sa.BigInteger(), nullable=True)
    )
    op.execute(
        "UPDATE publication_targets AS t SET channel_id = c.id "
        "FROM publishing_channels AS c WHERE c.inbox_id = t.inbox_id"
    )
    op.alter_column("publication_targets", "channel_id", nullable=False)
    op.drop_constraint(
        "uniq_publication_targets_publication_inbox", "publication_targets", type_="unique"
    )
    op.drop_index(
        "index_publication_targets_on_account_id_and_inbox_id",
        table_name="publication_targets",
    )
    op.drop_column("publication_targets", "inbox_id")
    op.create_foreign_key(
        "publication_targets_channel_id_fkey",
        "publication_targets",
        "publishing_channels",
        ["channel_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uniq_publication_targets_publication_channel",
        "publication_targets",
        ["publication_id", "channel_id"],
    )
    op.create_index(
        "index_publication_targets_on_account_id_and_channel_id",
        "publication_targets",
        ["account_id", "channel_id"],
    )

    # channel_metric_snapshots: inbox_id -> channel_id
    op.add_column(
        "channel_metric_snapshots", sa.Column("channel_id", sa.BigInteger(), nullable=True)
    )
    op.execute(
        "UPDATE channel_metric_snapshots AS s SET channel_id = c.id "
        "FROM publishing_channels AS c WHERE c.inbox_id = s.inbox_id"
    )
    op.alter_column("channel_metric_snapshots", "channel_id", nullable=False)
    op.drop_constraint(
        "uniq_channel_metric_snapshots_inbox_date",
        "channel_metric_snapshots",
        type_="unique",
    )
    op.drop_column("channel_metric_snapshots", "inbox_id")
    op.create_foreign_key(
        "channel_metric_snapshots_channel_id_fkey",
        "channel_metric_snapshots",
        "publishing_channels",
        ["channel_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uniq_channel_metric_snapshots_channel_date",
        "channel_metric_snapshots",
        ["channel_id", "date"],
    )


def downgrade() -> None:
    # Rows of channels that have no inbox can't be expressed before this
    # revision.
    op.execute(
        "DELETE FROM channel_metric_snapshots WHERE channel_id IN "
        "(SELECT id FROM publishing_channels WHERE inbox_id IS NULL)"
    )
    op.execute(
        "DELETE FROM publication_targets WHERE channel_id IN "
        "(SELECT id FROM publishing_channels WHERE inbox_id IS NULL)"
    )

    op.add_column(
        "channel_metric_snapshots", sa.Column("inbox_id", sa.BigInteger(), nullable=True)
    )
    op.execute(
        "UPDATE channel_metric_snapshots AS s SET inbox_id = c.inbox_id "
        "FROM publishing_channels AS c WHERE c.id = s.channel_id"
    )
    op.alter_column("channel_metric_snapshots", "inbox_id", nullable=False)
    op.drop_constraint(
        "uniq_channel_metric_snapshots_channel_date",
        "channel_metric_snapshots",
        type_="unique",
    )
    op.drop_constraint(
        "channel_metric_snapshots_channel_id_fkey",
        "channel_metric_snapshots",
        type_="foreignkey",
    )
    op.drop_column("channel_metric_snapshots", "channel_id")
    op.create_foreign_key(
        "channel_metric_snapshots_inbox_id_fkey",
        "channel_metric_snapshots",
        "inboxes",
        ["inbox_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uniq_channel_metric_snapshots_inbox_date",
        "channel_metric_snapshots",
        ["inbox_id", "date"],
    )

    op.add_column(
        "publication_targets", sa.Column("inbox_id", sa.BigInteger(), nullable=True)
    )
    op.execute(
        "UPDATE publication_targets AS t SET inbox_id = c.inbox_id "
        "FROM publishing_channels AS c WHERE c.id = t.channel_id"
    )
    op.alter_column("publication_targets", "inbox_id", nullable=False)
    op.drop_index(
        "index_publication_targets_on_account_id_and_channel_id",
        table_name="publication_targets",
    )
    op.drop_constraint(
        "uniq_publication_targets_publication_channel",
        "publication_targets",
        type_="unique",
    )
    op.drop_constraint(
        "publication_targets_channel_id_fkey", "publication_targets", type_="foreignkey"
    )
    op.drop_column("publication_targets", "channel_id")
    op.create_foreign_key(
        "publication_targets_inbox_id_fkey",
        "publication_targets",
        "inboxes",
        ["inbox_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uniq_publication_targets_publication_inbox",
        "publication_targets",
        ["publication_id", "inbox_id"],
    )
    op.create_index(
        "index_publication_targets_on_account_id_and_inbox_id",
        "publication_targets",
        ["account_id", "inbox_id"],
    )

    op.drop_index(
        "uniq_publishing_channels_account_network_external",
        table_name="publishing_channels",
    )
    op.drop_index("ix_publishing_channels_account_id", table_name="publishing_channels")
    op.drop_table("publishing_channels")
