"""phase5f: channel_twilio_sms

Adds the table backing ``Channel::TwilioSms``. See
:class:`app.domains.inboxes.models.TwilioSmsChannel` for the
field-level rationale.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-06 19:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_twilio_sms",
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
        sa.Column("account_sid", sa.String(), nullable=False),
        sa.Column("auth_token", sa.String(), nullable=False),
        sa.Column("api_key_sid", sa.String(), nullable=True),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("messaging_service_sid", sa.String(), nullable=True),
        sa.Column(
            "medium", sa.Integer(), server_default="0", nullable=True
        ),
        sa.Column(
            "content_templates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "content_templates_last_updated",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_channel_twilio_sms_on_phone_number",
        "channel_twilio_sms",
        ["phone_number"],
        unique=True,
    )
    op.create_index(
        "index_channel_twilio_sms_on_messaging_service_sid",
        "channel_twilio_sms",
        ["messaging_service_sid"],
        unique=True,
    )
    op.create_index(
        "index_channel_twilio_sms_on_account_sid_and_phone_number",
        "channel_twilio_sms",
        ["account_sid", "phone_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "index_channel_twilio_sms_on_account_sid_and_phone_number",
        table_name="channel_twilio_sms",
    )
    op.drop_index(
        "index_channel_twilio_sms_on_messaging_service_sid",
        table_name="channel_twilio_sms",
    )
    op.drop_index(
        "index_channel_twilio_sms_on_phone_number",
        table_name="channel_twilio_sms",
    )
    op.drop_table("channel_twilio_sms")
