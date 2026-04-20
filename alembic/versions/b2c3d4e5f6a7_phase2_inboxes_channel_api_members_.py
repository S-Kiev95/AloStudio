"""phase2_inboxes_channel_api_inbox_members_teams_team_members

Revision ID: b2c3d4e5f6a7
Revises: eb5b562ecc47
Create Date: 2026-04-19 00:00:00.000000

Hand-written (Docker was down when Phase 2 landed, so autogenerate wasn't
run). Mirrors the autogenerate style of Phase 1 exactly: server defaults,
nullability, index names, and PK/FK constraint shape are derived directly
from the SQLModel definitions in ``app.domains.inboxes.models`` and
``app.domains.teams.models`` — which in turn mirror
``reference/chatwoot/db/schema.rb`` column-for-column.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: str | Sequence[str] | None = 'eb5b562ecc47'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ channel_api
    op.create_table(
        'channel_api',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('webhook_url', sa.String(), nullable=True),
        sa.Column('identifier', sa.String(), nullable=True),
        sa.Column('hmac_token', sa.String(), nullable=True),
        sa.Column('secret', sa.String(), nullable=True),
        sa.Column('hmac_mandatory', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('additional_attributes', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('identifier'),
        sa.UniqueConstraint('hmac_token'),
    )

    # ------------------------------------------------------------------ inboxes
    op.create_table(
        'inboxes',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('channel_type', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('business_name', sa.String(), nullable=True),
        sa.Column('email_address', sa.String(), nullable=True),
        sa.Column('enable_auto_assignment', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('enable_email_collect', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('greeting_enabled', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('greeting_message', sa.String(), nullable=True),
        sa.Column('working_hours_enabled', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('out_of_office_message', sa.String(), nullable=True),
        sa.Column('timezone', sa.String(), server_default='UTC', nullable=True),
        sa.Column('csat_survey_enabled', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('allow_messages_after_resolved', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('lock_to_single_conversation', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('sender_name_type', sa.Integer(), server_default='0', nullable=False),
        sa.Column('auto_assignment_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('csat_config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('portal_id', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('index_inboxes_on_account_id', 'inboxes', ['account_id'], unique=False)
    op.create_index(
        'index_inboxes_on_channel_id_and_channel_type',
        'inboxes',
        ['channel_id', 'channel_type'],
        unique=False,
    )
    op.create_index('index_inboxes_on_portal_id', 'inboxes', ['portal_id'], unique=False)

    # ------------------------------------------------------------------ inbox_members
    op.create_table(
        'inbox_members',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('inbox_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['inbox_id'], ['inboxes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inbox_id', 'user_id', name='index_inbox_members_on_inbox_id_and_user_id'),
    )
    op.create_index('index_inbox_members_on_inbox_id', 'inbox_members', ['inbox_id'], unique=False)

    # ------------------------------------------------------------------ teams
    op.create_table(
        'teams',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('allow_auto_assign', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('account_id', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'account_id', name='index_teams_on_name_and_account_id'),
    )
    op.create_index('index_teams_on_account_id', 'teams', ['account_id'], unique=False)

    # ------------------------------------------------------------------ team_members
    op.create_table(
        'team_members',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('team_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'user_id', name='index_team_members_on_team_id_and_user_id'),
    )
    op.create_index('index_team_members_on_team_id', 'team_members', ['team_id'], unique=False)
    op.create_index('index_team_members_on_user_id', 'team_members', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('index_team_members_on_user_id', table_name='team_members')
    op.drop_index('index_team_members_on_team_id', table_name='team_members')
    op.drop_table('team_members')

    op.drop_index('index_teams_on_account_id', table_name='teams')
    op.drop_table('teams')

    op.drop_index('index_inbox_members_on_inbox_id', table_name='inbox_members')
    op.drop_table('inbox_members')

    op.drop_index('index_inboxes_on_portal_id', table_name='inboxes')
    op.drop_index('index_inboxes_on_channel_id_and_channel_type', table_name='inboxes')
    op.drop_index('index_inboxes_on_account_id', table_name='inboxes')
    op.drop_table('inboxes')

    op.drop_table('channel_api')
