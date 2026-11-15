"""calls: recording and transcription of WhatsApp calls (F7)

Revision ID: e0f1a2b3c4d6
Revises: d9e0f1a2b3c5
Create Date: 2026-11-14 20:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e0f1a2b3c4d6"
down_revision: str | None = "d9e0f1a2b3c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CALL_COLUMNS = (
    sa.Column("recording_requested", sa.Boolean(), server_default="false", nullable=False),
    sa.Column("transcription_requested", sa.Boolean(), server_default="false", nullable=False),
    sa.Column("recording_media_id", sa.String(), nullable=True),
    sa.Column("recording_available_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("recording_attachment_id", sa.BigInteger(), nullable=True),
    sa.Column("transcript_media_id", sa.String(), nullable=True),
    sa.Column("transcript_available_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("transcript", sa.JSON(), nullable=True),
    sa.Column("transcript_language", sa.String(16), nullable=True),
)


def upgrade() -> None:
    for column in _CALL_COLUMNS:
        op.add_column("calls", column)
    op.create_table(
        "call_inbox_settings",
        sa.Column(
            "inbox_id",
            sa.BigInteger(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("transcribe", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("purpose", sa.String(250), nullable=True),
        sa.Column("announcement_language", sa.String(8), server_default="es", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("call_inbox_settings")
    for column in reversed(_CALL_COLUMNS):
        op.drop_column("calls", column.name)
