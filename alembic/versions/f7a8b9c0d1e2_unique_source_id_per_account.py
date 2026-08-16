"""one row per provider message id, enforced by the database

An Instagram auto-reply landed twice in a real thread: the worker recorded
the DM it had just sent while Meta's echo of that same send arrived over
the webhook, 0.4s apart. Both paths dedupe on ``source_id`` — and both
read before the other committed, so neither saw the other. A SELECT
followed by an INSERT cannot close that; only a constraint can.

Partial, because ``source_id`` is null for everything an agent writes
here — most rows — and those are not duplicates of each other. Scoped to
the account because that is already the pair both dedupe checks use.

The cleanup keeps the earliest of each duplicate group, which is what a
working dedupe would have left, and first carries over the
``automation`` marker if only the later row had it — otherwise
deduplicating would quietly turn an automated reply into one that looks
hand-written.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None

INDEX = "index_messages_on_account_and_source_id"


def upgrade() -> None:
    # Carry the automation marker back onto the row we are about to keep.
    # ``content_attributes`` is ``json``, not ``jsonb`` — Chatwoot's schema,
    # mirrored — so the merge round-trips through jsonb, which is the type
    # that has a concatenation operator.
    op.execute(
        """
        UPDATE messages keeper
        SET content_attributes = (
            keeper.content_attributes::jsonb
            || jsonb_build_object(
                'automation', loser.content_attributes->>'automation',
                'instagram_comment_id',
                loser.content_attributes->>'instagram_comment_id'
            )
        )::json
        FROM messages loser
        WHERE loser.account_id = keeper.account_id
          AND loser.source_id = keeper.source_id
          AND loser.id > keeper.id
          AND keeper.source_id IS NOT NULL
          AND keeper.content_attributes->>'automation' IS NULL
          AND loser.content_attributes->>'automation' IS NOT NULL
        """
    )
    op.execute(
        """
        DELETE FROM messages m
        USING messages keeper
        WHERE m.account_id = keeper.account_id
          AND m.source_id = keeper.source_id
          AND m.source_id IS NOT NULL
          AND m.id > keeper.id
        """
    )
    op.create_index(
        INDEX,
        "messages",
        ["account_id", "source_id"],
        unique=True,
        postgresql_where=sa.text("source_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="messages")
