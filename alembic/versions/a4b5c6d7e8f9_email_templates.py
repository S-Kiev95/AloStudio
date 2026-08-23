"""letterheads an organisation can reuse across mailboxes

A mailbox carried its own single ``template_html``: three mailboxes meant
three copies of the same design, and an organisation that wanted one look
for a welcome and another for a resolution notice had nowhere to put the
second.

``channel_email.template_html`` stays exactly where it is and keeps
working. A mailbox that points at a shared template uses that instead;
one that does not renders as it always has. Nothing is migrated, because
guessing which of several identical letterheads was "the" shared one is
a guess, and a wrong one changes what customers receive.

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "template_html", sa.String(), server_default="", nullable=False
        ),
        sa.Column(
            "template_design",
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
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "name", name="uq_email_templates_account_name"
        ),
    )
    op.create_index(
        "ix_email_templates_account_id", "email_templates", ["account_id"]
    )

    op.add_column(
        "channel_email",
        sa.Column("email_template_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_channel_email_email_template_id",
        "channel_email",
        ["email_template_id"],
    )
    # SET NULL rather than CASCADE: deleting a shared template must not
    # delete the mailbox with it. The mailbox falls back to its own
    # ``template_html``, which is the pre-shared-template behaviour.
    op.create_foreign_key(
        "fk_channel_email_email_template_id",
        "channel_email",
        "email_templates",
        ["email_template_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_channel_email_email_template_id", "channel_email", type_="foreignkey"
    )
    op.drop_index(
        "ix_channel_email_email_template_id", table_name="channel_email"
    )
    op.drop_column("channel_email", "email_template_id")
    op.drop_index("ix_email_templates_account_id", table_name="email_templates")
    op.drop_table("email_templates")
