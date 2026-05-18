"""Verify Phase 10.4's enterprise-schema sweep produced the three
tables (audits, sla_policies, applied_slas) so a pg_dump → pg_restore
from a Chatwoot reference works without column drift.

We don't ship SQLModel classes for these tables — only the schema.
Tests assert the tables exist + the parity-critical columns are
present.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def _columns(db_session, table: str) -> set[str]:
    rows = (
        await db_session.exec(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t"
            ).bindparams(t=table)
        )
    ).all()
    return {row[0] for row in rows}


async def test_audits_table_exists(db_session):
    cols = await _columns(db_session, "audits")
    expected = {
        "id",
        "auditable_id",
        "auditable_type",
        "associated_id",
        "associated_type",
        "user_id",
        "user_type",
        "username",
        "action",
        "audited_changes",
        "version",
        "comment",
        "remote_address",
        "request_uuid",
        "created_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


async def test_sla_policies_table_exists(db_session):
    cols = await _columns(db_session, "sla_policies")
    expected = {
        "id",
        "name",
        "first_response_time_threshold",
        "next_response_time_threshold",
        "resolution_time_threshold",
        "only_during_business_hours",
        "description",
        "account_id",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


async def test_applied_slas_table_exists(db_session):
    cols = await _columns(db_session, "applied_slas")
    expected = {
        "id",
        "account_id",
        "sla_policy_id",
        "conversation_id",
        "sla_status",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


async def test_applied_slas_unique_composite_constraint(db_session):
    """The unique (account_id, sla_policy_id, conversation_id) index is
    parity-critical — Rails relies on it to prevent double-apply."""
    rows = (
        await db_session.exec(
            text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'applied_slas'"
            )
        )
    ).all()
    names = {row[0] for row in rows}
    assert (
        "index_applied_slas_on_account_sla_policy_conversation"
        in names
    )
