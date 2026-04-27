"""phase5a: channel_web_widgets

Adds the table backing ``Channel::WebWidget`` — the embedded JS chat
widget. See :class:`app.domains.inboxes.models.WebWidget` for the
field-level rationale.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-04-26 13:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e9f0a1b2c3d4"
down_revision: str | Sequence[str] | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_web_widgets",
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
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("website_url", sa.String(), nullable=False),
        sa.Column(
            "widget_color",
            sa.String(),
            server_default="#1f93ff",
            nullable=False,
        ),
        sa.Column("welcome_title", sa.String(), nullable=True),
        sa.Column("welcome_tagline", sa.String(), nullable=True),
        sa.Column("website_token", sa.String(), nullable=False),
        sa.Column("hmac_token", sa.String(), nullable=False),
        sa.Column(
            "hmac_mandatory",
            sa.Boolean(),
            server_default="false",
            nullable=True,
        ),
        sa.Column(
            "pre_chat_form_enabled",
            sa.Boolean(),
            server_default="false",
            nullable=True,
        ),
        sa.Column(
            "pre_chat_form_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "continuity_via_email",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "feature_flags",
            sa.Integer(),
            server_default="7",
            nullable=False,
        ),
        sa.Column(
            "reply_time", sa.Integer(), server_default="0", nullable=True
        ),
        sa.Column(
            "allowed_domains",
            sa.Text(),
            server_default="",
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_channel_web_widgets_on_website_token",
        "channel_web_widgets",
        ["website_token"],
        unique=True,
    )
    op.create_index(
        "index_channel_web_widgets_on_hmac_token",
        "channel_web_widgets",
        ["hmac_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "index_channel_web_widgets_on_hmac_token",
        table_name="channel_web_widgets",
    )
    op.drop_index(
        "index_channel_web_widgets_on_website_token",
        table_name="channel_web_widgets",
    )
    op.drop_table("channel_web_widgets")
