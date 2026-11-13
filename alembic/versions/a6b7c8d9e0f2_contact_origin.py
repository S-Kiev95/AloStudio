"""crm: contact origin (F11)

Where each person first came from. New contacts get it from their first
conversation; this fills the ones that already exist the same way: the
channel of their oldest conversation, or the ad/post/short link Meta
reported on it.

Revision ID: a6b7c8d9e0f2
Revises: 1a2f8e3b4c5d
Create Date: 2026-11-13 21:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a6b7c8d9e0f2"
down_revision: str | None = "1a2f8e3b4c5d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    ("source", sa.String()),
    ("source_channel", sa.String()),
    ("source_detail", sa.String()),
    ("source_ad_id", sa.String()),
    ("source_conversation_id", sa.BigInteger()),
    ("source_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        op.add_column("contacts", sa.Column(name, type_, nullable=True))
    op.create_index(
        "index_contacts_on_account_id_and_source", "contacts", ["account_id", "source"]
    )
    op.execute(
        """
        WITH first AS (
            SELECT DISTINCT ON (c.contact_id)
                   c.contact_id, c.id, c.created_at, c.ad_source, c.ad_id,
                   c.ad_headline, i.channel_type
              FROM conversations c
              JOIN inboxes i ON i.id = c.inbox_id
             ORDER BY c.contact_id, c.created_at, c.id
        )
        UPDATE contacts AS ct
           SET source = CASE
                   WHEN f.ad_id IS NOT NULL OR f.ad_source IS NOT NULL THEN
                       CASE WHEN f.ad_source IN ('ad', 'post', 'shortlink')
                            THEN f.ad_source ELSE 'ad' END
                   ELSE 'channel' END,
               source_channel = CASE f.channel_type
                   WHEN 'Channel::Whatsapp' THEN 'whatsapp'
                   WHEN 'Channel::Instagram' THEN 'instagram'
                   WHEN 'Channel::FacebookPage' THEN 'facebook'
                   WHEN 'Channel::WebWidget' THEN 'web'
                   WHEN 'Channel::Email' THEN 'email'
                   WHEN 'Channel::Telegram' THEN 'telegram'
                   WHEN 'Channel::Sms' THEN 'sms'
                   WHEN 'Channel::TwilioSms' THEN 'sms'
                   WHEN 'Channel::Api' THEN 'api'
               END,
               source_detail = f.ad_headline,
               source_ad_id = f.ad_id,
               source_conversation_id = f.id,
               source_at = f.created_at
          FROM first f
         WHERE f.contact_id = ct.id AND ct.source IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("index_contacts_on_account_id_and_source", table_name="contacts")
    for name, _ in reversed(_COLUMNS):
        op.drop_column("contacts", name)
