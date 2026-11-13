"""crm: sales pipelines, stages and opportunities (F11)

Revision ID: d3e4f5a6b7c9
Revises: c2d3e4f5a6b8
Create Date: 2026-11-13 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d3e4f5a6b7c9"
down_revision: str | None = "c2d3e4f5a6b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "crm_pipelines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("rotten_days", sa.Integer(), server_default="30", nullable=False),
        *_timestamps(),
    )
    op.create_index("index_crm_pipelines_on_account_id", "crm_pipelines", ["account_id"])

    op.create_table(
        "crm_stages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("pipeline_id", sa.BigInteger(), sa.ForeignKey("crm_pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(32), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("kind", sa.String(8), server_default="open", nullable=False),
        sa.Column("probability", sa.Integer(), server_default="0", nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
    )
    op.create_index("index_crm_stages_on_pipeline_id", "crm_stages", ["pipeline_id"])

    op.create_table(
        "crm_opportunities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline_id", sa.BigInteger(), sa.ForeignKey("crm_pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.BigInteger(), sa.ForeignKey("crm_stages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("value", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", sa.BigInteger(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expected_close_on", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.Text(), nullable=True),
        sa.Column("position", sa.Float(), server_default="0", nullable=False),
        sa.Column("stage_changed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("index_crm_opportunities_on_account_id", "crm_opportunities", ["account_id"])
    op.create_index("index_crm_opportunities_on_stage_id", "crm_opportunities", ["stage_id"])
    op.create_index("index_crm_opportunities_on_contact_id", "crm_opportunities", ["contact_id"])


def downgrade() -> None:
    op.drop_table("crm_opportunities")
    op.drop_table("crm_stages")
    op.drop_table("crm_pipelines")
