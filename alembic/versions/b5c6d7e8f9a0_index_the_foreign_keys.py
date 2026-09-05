"""index every foreign key that had none

Postgres indexes a primary key and a unique constraint on its own. It
does **not** index a foreign key. Thirty of ours had no index on the
referencing column, which means two things get slower as the tables
fill: any join through that key, and — less obvious — every delete on
the *parent* row, because Postgres has to scan the child table in full
to enforce the constraint.

None of this hurts today: the largest of these tables has a few hundred
rows and the planner correctly prefers a sequential scan. It is written
now because the cost arrives quietly and late, and because a
``CREATE INDEX`` on an empty table is free while the same index on a
million rows is a maintenance window.

The list came from querying ``pg_constraint`` against the running
database rather than from reading the models, so it reflects what the
schema actually has.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
"""

from __future__ import annotations

from alembic import op

revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None

# (table, column) — the referencing side, which is the one that needs it.
FOREIGN_KEYS: tuple[tuple[str, str], ...] = (
    ("account_users", "inviter_id"),
    ("agent_bot_inboxes", "account_id"),
    ("agent_bot_inboxes", "agent_bot_id"),
    ("agent_bot_inboxes", "inbox_id"),
    ("articles", "category_id"),
    ("categories", "account_id"),
    ("categories", "portal_id"),
    ("channel_api", "account_id"),
    ("channel_email", "account_id"),
    ("channel_facebook_pages", "account_id"),
    ("channel_instagram", "account_id"),
    ("channel_sms", "account_id"),
    ("channel_telegram", "account_id"),
    ("channel_twilio_sms", "account_id"),
    ("channel_web_widgets", "account_id"),
    ("channel_whatsapp", "account_id"),
    ("conversation_participants", "account_id"),
    ("inbox_members", "user_id"),
    ("instagram_comments", "account_id"),
    ("instagram_post_autoreplies", "account_id"),
    ("instagram_posts", "inbox_id"),
    ("integrations_hooks", "account_id"),
    ("integrations_hooks", "inbox_id"),
    ("macros", "created_by_id"),
    ("macros", "updated_by_id"),
    ("mcp_tokens", "user_id"),
    ("mentions", "account_id"),
    ("notification_settings", "user_id"),
    ("portals", "account_id"),
    ("webhooks", "inbox_id"),
)


def _name(table: str, column: str) -> str:
    return f"ix_{table}_{column}"


def upgrade() -> None:
    for table, column in FOREIGN_KEYS:
        op.create_index(_name(table, column), table, [column])


def downgrade() -> None:
    for table, column in reversed(FOREIGN_KEYS):
        op.drop_index(_name(table, column), table_name=table)
