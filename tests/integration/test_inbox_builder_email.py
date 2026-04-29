"""Integration tests for the EmailChannel branch of :class:`InboxBuilder`.

The email channel doubles the surface of the WebWidget branch (IMAP +
SMTP triplets + verification flag), so we pin the validation matrix
plus the happy path here. The actual IMAP/SMTP wire round-trips
arrive with milestones 5b.3 / 5b.4.
"""

from __future__ import annotations

import pytest

from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import (
    CHANNEL_TYPE_EMAIL,
    EmailChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

pytestmark = pytest.mark.integration


async def _make_account(db_session, suffix: str = ""):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@em.example.com",
            account_name=f"Em{suffix}",
            user_full_name=f"Em Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def test_creates_email_channel_with_minimal_params(db_session):
    """``email`` is the only required field. SMTP/IMAP both ship
    disabled by default — the inbox is in a "configured but inert"
    state until the agent enables and sets the host triplet."""
    owner = await _make_account(db_session)

    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Support Email",
            channel_type="email",
            channel_params={"email": "support@example.com"},
        ),
    ).perform()

    assert result.inbox.channel_type == CHANNEL_TYPE_EMAIL
    assert isinstance(result.channel, EmailChannel)
    ch = result.channel
    # Email is lowercased on store (Rails: ``before_save :downcase``).
    assert ch.email == "support@example.com"
    # forward_to_email auto-generated when not supplied.
    assert ch.forward_to_email and "@" in ch.forward_to_email
    assert ch.imap_enabled is False
    assert ch.smtp_enabled is False
    assert ch.verified_for_sending is False
    # OAuth fields default to empty so the schema is forward-compat
    # with Phase 9.
    assert ch.provider is None
    assert ch.provider_config == {} or ch.provider_config is None


async def test_email_is_lowercased(db_session):
    owner = await _make_account(db_session, suffix="-lower")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Mixed",
            channel_type="email",
            channel_params={"email": "Support@Example.COM"},
        ),
    ).perform()
    assert result.channel.email == "support@example.com"


async def test_rejects_missing_email(db_session):
    owner = await _make_account(db_session, suffix="-noem")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Bad",
                channel_type="email",
                channel_params={},
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "email" in exc_info.value.detail.get("attributes", [])


async def test_imap_enabled_requires_host_triplet(db_session):
    owner = await _make_account(db_session, suffix="-imap")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Half-IMAP",
                channel_type="email",
                channel_params={
                    "email": "imap@example.com",
                    "imap_enabled": True,
                    "imap_address": "imap.example.com",
                    # Missing imap_port + imap_login → 422.
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    attrs = exc_info.value.detail.get("attributes", [])
    assert "imap_port" in attrs or "imap_login" in attrs


async def test_smtp_enabled_requires_host_triplet(db_session):
    owner = await _make_account(db_session, suffix="-smtp")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Half-SMTP",
                channel_type="email",
                channel_params={
                    "email": "smtp@example.com",
                    "smtp_enabled": True,
                    # All triplet fields missing → first one (smtp_address) flagged.
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "smtp_address" in exc_info.value.detail.get("attributes", [])


async def test_full_imap_and_smtp_config_round_trips(db_session):
    """Happy path with both sides enabled — the wire-level send/receive
    is covered by 5b.3 and 5b.4; here we only assert the row persists
    with every column set the way the caller provided."""
    owner = await _make_account(db_session, suffix="-full")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Full Email",
            channel_type="email",
            channel_params={
                "email": "ops@example.com",
                "imap_enabled": True,
                "imap_address": "imap.example.com",
                "imap_port": 993,
                "imap_login": "ops@example.com",
                "imap_password": "secret-imap",
                "imap_enable_ssl": True,
                "smtp_enabled": True,
                "smtp_address": "smtp.example.com",
                "smtp_port": 587,
                "smtp_login": "ops@example.com",
                "smtp_password": "secret-smtp",
                "smtp_domain": "example.com",
                "smtp_enable_starttls_auto": True,
            },
        ),
    ).perform()
    ch = result.channel
    assert isinstance(ch, EmailChannel)
    assert ch.imap_enabled is True
    assert ch.imap_address == "imap.example.com"
    assert ch.imap_port == 993
    assert ch.imap_login == "ops@example.com"
    assert ch.smtp_enabled is True
    assert ch.smtp_port == 587


async def test_email_uniqueness_returns_422(db_session):
    """The unique index on ``email`` surfaces as a 422 envelope."""
    owner = await _make_account(db_session, suffix="-uniq")
    await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="First",
            channel_type="email",
            channel_params={"email": "dup@example.com"},
        ),
    ).perform()

    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Second",
                channel_type="email",
                channel_params={"email": "dup@example.com"},
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "already taken" in exc_info.value.detail["message"]
