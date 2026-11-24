"""email: personal templates, rich org/user signatures, and user job title

Adds:
  * ``email_templates.user_id`` (nullable FK to ``users.id``) and
    ``email_templates.is_default`` (personal default template per user/account).
    Replaces ``uq_email_templates_account_name`` with two partial unique
    indexes so names stay unique per account for organisation templates and
    per (account, user) for personal templates, plus at most one default
    personal template per (account, user).
  * ``email_signatures`` table holding one organisation signature per account
    (``user_id IS NULL``) and one personal signature per (account, user), each
    with HTML, plain text and canvas design JSONB.
  * ``users.job_title`` so signatures can interpolate the user's role/title
    (``{{cargo}}``) alongside their existing name, email, phone and avatar.

Revision ID: f5b7d9e1a3c5
Revises: e4a6c8b0d2f4
Create Date: 2026-11-24 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f5b7d9e1a3c5"
down_revision: str | None = "e4a6c8b0d2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Personal email templates on email_templates
    op.add_column(
        "email_templates",
        sa.Column("user_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "email_templates",
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_foreign_key(
        "fk_email_templates_user_id",
        "email_templates",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_email_templates_user_id", "email_templates", ["user_id"])

    op.drop_constraint("uq_email_templates_account_name", "email_templates", type_="unique")
    op.create_index(
        "uq_email_templates_account_org_name",
        "email_templates",
        ["account_id", "name"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL"),
    )
    op.create_index(
        "uq_email_templates_account_user_name",
        "email_templates",
        ["account_id", "user_id", "name"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_email_templates_user_default",
        "email_templates",
        ["account_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL AND is_default = true"),
    )

    # 2. Rich email signatures (org + per-user)
    op.create_table(
        "email_signatures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("signature_html", sa.String(), server_default="", nullable=False),
        sa.Column("signature_text", sa.String(), server_default="", nullable=False),
        sa.Column(
            "signature_design",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
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
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_signatures_account_id", "email_signatures", ["account_id"])
    op.create_index("ix_email_signatures_user_id", "email_signatures", ["user_id"])
    op.create_index(
        "uq_email_signatures_org",
        "email_signatures",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL"),
    )
    op.create_index(
        "uq_email_signatures_user",
        "email_signatures",
        ["account_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    # 3. User job title ("cargo") for signature variables
    op.add_column("users", sa.Column("job_title", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "job_title")

    op.drop_index("uq_email_signatures_user", table_name="email_signatures")
    op.drop_index("uq_email_signatures_org", table_name="email_signatures")
    op.drop_index("ix_email_signatures_user_id", table_name="email_signatures")
    op.drop_index("ix_email_signatures_account_id", table_name="email_signatures")
    op.drop_table("email_signatures")

    op.drop_index("uq_email_templates_user_default", table_name="email_templates")
    op.drop_index("uq_email_templates_account_user_name", table_name="email_templates")
    op.drop_index("uq_email_templates_account_org_name", table_name="email_templates")
    # Remove any personal rows before restoring the (account_id, name) uniqueness
    # constraint so downgrade succeeds cleanly even when personal templates exist.
    op.execute(sa.text("DELETE FROM email_templates WHERE user_id IS NOT NULL"))
    op.create_unique_constraint(
        "uq_email_templates_account_name",
        "email_templates",
        ["account_id", "name"],
    )
    op.drop_index("ix_email_templates_user_id", table_name="email_templates")
    op.drop_constraint("fk_email_templates_user_id", "email_templates", type_="foreignkey")
    op.drop_column("email_templates", "is_default")
    op.drop_column("email_templates", "user_id")
