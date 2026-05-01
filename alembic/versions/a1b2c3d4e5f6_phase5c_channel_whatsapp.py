"""phase5c: channel_whatsapp

Adds the table backing ``Channel::Whatsapp`` — supports both Meta's
Cloud API (``provider='whatsapp_cloud'``) and 360dialog
(``provider='default'``). See
:class:`app.domains.inboxes.models.WhatsappChannel` for the
field-level rationale.

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-05-01 03:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_whatsapp",
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
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=False),
        sa.Column(
            "provider",
            sa.String(),
            server_default="default",
            nullable=True,
        ),
        sa.Column(
            "provider_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "message_templates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "message_templates_last_updated",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_channel_whatsapp_on_phone_number",
        "channel_whatsapp",
        ["phone_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "index_channel_whatsapp_on_phone_number",
        table_name="channel_whatsapp",
    )
    op.drop_table("channel_whatsapp")
