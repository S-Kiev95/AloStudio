"""phase4a: conversations, messages, attachments, mentions, conversation_participants

Creates the core Phase 4 tables + Chatwoot's per-account
``conv_dpid_seq_<account_id>`` sequence and ``BEFORE INSERT`` trigger
that assigns ``display_id`` atomically.

Revision ID: c7a8d1e3f4b9
Revises: b6166907e906
Create Date: 2026-04-21 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c7a8d1e3f4b9"
down_revision: str | Sequence[str] | None = "b6166907e906"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# display_id trigger — ported from Chatwoot's
# db/functions/camo_bin_v1.sql + the ``trigger.before(:insert)`` declared on
# ``Conversation``. The sequence is per-account and created as a side-effect
# of creating an Account (``Account#ensure_conversation_sequence`` in Ruby
# — we replicate that via an accounts ``AFTER INSERT`` trigger below).
# ---------------------------------------------------------------------------
_CREATE_CONVERSATION_DISPLAY_ID_FN = """
CREATE OR REPLACE FUNCTION conversations_before_insert_row_tr()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.display_id := nextval('conv_dpid_seq_' || NEW.account_id);
  RETURN NEW;
END;
$$;
"""

_DROP_CONVERSATION_DISPLAY_ID_FN = "DROP FUNCTION IF EXISTS conversations_before_insert_row_tr();"

_CREATE_ACCOUNT_SEQ_FN = """
CREATE OR REPLACE FUNCTION accounts_after_insert_row_tr()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  EXECUTE format('CREATE SEQUENCE IF NOT EXISTS conv_dpid_seq_%s', NEW.id);
  RETURN NEW;
END;
$$;
"""

_DROP_ACCOUNT_SEQ_FN = "DROP FUNCTION IF EXISTS accounts_after_insert_row_tr();"


def upgrade() -> None:
    # pgcrypto for ``gen_random_uuid()`` (Chatwoot also enables this).
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ------------------------------------------------------------------
    # conversations
    # ------------------------------------------------------------------
    op.create_table(
        "conversations",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("inbox_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("contact_inbox_id", sa.BigInteger(), nullable=True),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.BigInteger(), nullable=True),
        sa.Column("assignee_agent_bot_id", sa.BigInteger(), nullable=True),
        sa.Column("campaign_id", sa.BigInteger(), nullable=True),
        sa.Column("sla_policy_id", sa.BigInteger(), nullable=True),
        sa.Column("display_id", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "uuid",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("status", sa.Integer(), server_default="0", nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent_last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignee_last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contact_last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waiting_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_reply_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "additional_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "custom_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("cached_label_list", sa.Text(), nullable=True),
        sa.Column("identifier", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inbox_id"], ["inboxes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_inbox_id"], ["contact_inboxes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("conv_acid_inbid_stat_asgnid_idx", "conversations", ["account_id", "inbox_id", "status", "assignee_id"])
    op.create_index("index_conversations_on_account_id", "conversations", ["account_id"])
    op.create_index("index_conversations_on_account_id_and_display_id", "conversations", ["account_id", "display_id"], unique=True)
    op.create_index("index_conversations_on_assignee_id_and_account_id", "conversations", ["assignee_id", "account_id"])
    op.create_index("index_conversations_on_campaign_id", "conversations", ["campaign_id"])
    op.create_index("index_conversations_on_contact_id", "conversations", ["contact_id"])
    op.create_index("index_conversations_on_contact_inbox_id", "conversations", ["contact_inbox_id"])
    op.create_index("index_conversations_on_first_reply_created_at", "conversations", ["first_reply_created_at"])
    op.create_index("index_conversations_on_id_and_account_id", "conversations", ["account_id", "id"])
    op.create_index("index_conversations_on_identifier_and_account_id", "conversations", ["identifier", "account_id"])
    op.create_index("index_conversations_on_inbox_id", "conversations", ["inbox_id"])
    op.create_index("index_conversations_on_priority", "conversations", ["priority"])
    op.create_index("index_conversations_on_status_and_account_id", "conversations", ["status", "account_id"])
    op.create_index("index_conversations_on_status_and_priority", "conversations", ["status", "priority"])
    op.create_index("index_conversations_on_team_id", "conversations", ["team_id"])
    op.create_index("index_conversations_on_uuid", "conversations", ["uuid"], unique=True)
    op.create_index("index_conversations_on_waiting_since", "conversations", ["waiting_since"])

    # Display-id trigger ---------------------------------------------------
    op.execute(_CREATE_CONVERSATION_DISPLAY_ID_FN)
    op.execute(
        "CREATE TRIGGER conversations_before_insert_row_tr "
        "BEFORE INSERT ON conversations "
        "FOR EACH ROW EXECUTE FUNCTION conversations_before_insert_row_tr();"
    )

    # Per-account sequence creation ---------------------------------------
    op.execute(_CREATE_ACCOUNT_SEQ_FN)
    op.execute(
        "CREATE TRIGGER accounts_after_insert_row_tr "
        "AFTER INSERT ON accounts "
        "FOR EACH ROW EXECUTE FUNCTION accounts_after_insert_row_tr();"
    )
    # Back-fill sequences for any accounts that already exist (Phase 1+
    # tests seed accounts; without this, conversation inserts would fail
    # with "relation conv_dpid_seq_N does not exist").
    op.execute(
        """
        DO $$
        DECLARE
          acct_id INT;
        BEGIN
          FOR acct_id IN SELECT id FROM accounts LOOP
            EXECUTE format('CREATE SEQUENCE IF NOT EXISTS conv_dpid_seq_%s', acct_id);
          END LOOP;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # messages
    # ------------------------------------------------------------------
    op.create_table(
        "messages",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("inbox_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("sender_type", sa.String(), nullable=True),
        sa.Column("sender_id", sa.BigInteger(), nullable=True),
        sa.Column("message_type", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.Integer(), server_default="0", nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("processed_message_content", sa.Text(), nullable=True),
        sa.Column(
            "content_attributes",
            postgresql.JSON(astext_type=sa.Text()),
            server_default="{}",
            nullable=True,
        ),
        sa.Column(
            "additional_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=True,
        ),
        sa.Column(
            "external_source_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=True,
        ),
        sa.Column(
            "sentiment",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=True,
        ),
        sa.Column("private", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inbox_id"], ["inboxes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_messages_account_content_created", "messages", ["account_id", "content_type", "created_at"])
    op.create_index("index_messages_on_account_created_type", "messages", ["account_id", "created_at", "message_type"])
    op.create_index("index_messages_on_account_id", "messages", ["account_id"])
    op.create_index("index_messages_on_account_id_and_inbox_id", "messages", ["account_id", "inbox_id"])
    op.create_index("index_messages_on_conversation_account_type_created", "messages", ["conversation_id", "account_id", "message_type", "created_at"])
    op.create_index("index_messages_on_conversation_id", "messages", ["conversation_id"])
    op.create_index("index_messages_on_created_at", "messages", ["created_at"])
    op.create_index("index_messages_on_inbox_id", "messages", ["inbox_id"])
    op.create_index("index_messages_on_sender_type_and_sender_id", "messages", ["sender_type", "sender_id"])
    op.create_index("index_messages_on_source_id", "messages", ["source_id"])

    # ------------------------------------------------------------------
    # attachments
    # ------------------------------------------------------------------
    op.create_table(
        "attachments",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.Integer(), server_default="0", nullable=True),
        sa.Column("extension", sa.String(), nullable=True),
        sa.Column("external_url", sa.String(), nullable=True),
        sa.Column("fallback_title", sa.String(), nullable=True),
        sa.Column("coordinates_lat", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("coordinates_long", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("index_attachments_on_account_id", "attachments", ["account_id"])
    op.create_index("index_attachments_on_message_id", "attachments", ["message_id"])

    # ------------------------------------------------------------------
    # mentions
    # ------------------------------------------------------------------
    op.create_table(
        "mentions",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("mentioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "conversation_id", name="index_mentions_on_user_id_and_conversation_id"),
    )
    op.create_index("index_mentions_on_conversation_id", "mentions", ["conversation_id"])
    op.create_index("index_mentions_on_user_id", "mentions", ["user_id"])

    # ------------------------------------------------------------------
    # conversation_participants
    # ------------------------------------------------------------------
    op.create_table(
        "conversation_participants",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "conversation_id",
            name="index_conversation_participants_on_user_and_conversation",
        ),
    )
    op.create_index("index_conversation_participants_on_conversation_id", "conversation_participants", ["conversation_id"])
    op.create_index("index_conversation_participants_on_user_id", "conversation_participants", ["user_id"])


def downgrade() -> None:
    op.drop_index("index_conversation_participants_on_user_id", table_name="conversation_participants")
    op.drop_index("index_conversation_participants_on_conversation_id", table_name="conversation_participants")
    op.drop_table("conversation_participants")

    op.drop_index("index_mentions_on_user_id", table_name="mentions")
    op.drop_index("index_mentions_on_conversation_id", table_name="mentions")
    op.drop_table("mentions")

    op.drop_index("index_attachments_on_message_id", table_name="attachments")
    op.drop_index("index_attachments_on_account_id", table_name="attachments")
    op.drop_table("attachments")

    op.drop_index("index_messages_on_source_id", table_name="messages")
    op.drop_index("index_messages_on_sender_type_and_sender_id", table_name="messages")
    op.drop_index("index_messages_on_inbox_id", table_name="messages")
    op.drop_index("index_messages_on_created_at", table_name="messages")
    op.drop_index("index_messages_on_conversation_id", table_name="messages")
    op.drop_index("index_messages_on_conversation_account_type_created", table_name="messages")
    op.drop_index("index_messages_on_account_id_and_inbox_id", table_name="messages")
    op.drop_index("index_messages_on_account_id", table_name="messages")
    op.drop_index("index_messages_on_account_created_type", table_name="messages")
    op.drop_index("idx_messages_account_content_created", table_name="messages")
    op.drop_table("messages")

    # Triggers on conversations + accounts
    op.execute("DROP TRIGGER IF EXISTS conversations_before_insert_row_tr ON conversations;")
    op.execute("DROP TRIGGER IF EXISTS accounts_after_insert_row_tr ON accounts;")
    op.execute(_DROP_CONVERSATION_DISPLAY_ID_FN)
    op.execute(_DROP_ACCOUNT_SEQ_FN)

    op.drop_index("index_conversations_on_waiting_since", table_name="conversations")
    op.drop_index("index_conversations_on_uuid", table_name="conversations")
    op.drop_index("index_conversations_on_team_id", table_name="conversations")
    op.drop_index("index_conversations_on_status_and_priority", table_name="conversations")
    op.drop_index("index_conversations_on_status_and_account_id", table_name="conversations")
    op.drop_index("index_conversations_on_priority", table_name="conversations")
    op.drop_index("index_conversations_on_inbox_id", table_name="conversations")
    op.drop_index("index_conversations_on_identifier_and_account_id", table_name="conversations")
    op.drop_index("index_conversations_on_id_and_account_id", table_name="conversations")
    op.drop_index("index_conversations_on_first_reply_created_at", table_name="conversations")
    op.drop_index("index_conversations_on_contact_inbox_id", table_name="conversations")
    op.drop_index("index_conversations_on_contact_id", table_name="conversations")
    op.drop_index("index_conversations_on_campaign_id", table_name="conversations")
    op.drop_index("index_conversations_on_assignee_id_and_account_id", table_name="conversations")
    op.drop_index("index_conversations_on_account_id_and_display_id", table_name="conversations")
    op.drop_index("index_conversations_on_account_id", table_name="conversations")
    op.drop_index("conv_acid_inbid_stat_asgnid_idx", table_name="conversations")
    op.drop_table("conversations")

    # Per-account sequences clean-up (best-effort).
    op.execute(
        """
        DO $$
        DECLARE r RECORD;
        BEGIN
          FOR r IN SELECT sequence_name FROM information_schema.sequences
                   WHERE sequence_name LIKE 'conv_dpid_seq_%' LOOP
            EXECUTE format('DROP SEQUENCE IF EXISTS %I', r.sequence_name);
          END LOOP;
        END $$;
        """
    )
