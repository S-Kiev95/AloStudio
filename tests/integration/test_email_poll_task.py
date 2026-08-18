"""The cron that makes inbound mail actually arrive.

``fetch_inbox_once`` was tested but unscheduled, so a correctly configured
mailbox received nothing until someone ran it by hand. What matters here is
which mailboxes the task picks up and that one bad mailbox cannot stop the
rest — a dead IMAP server is the normal failure, not the exceptional one.
"""

from __future__ import annotations

import pytest

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import EmailChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.workers import email_poll

pytestmark = pytest.mark.integration


@pytest.fixture
def ctx(db_session):
    """Bind the task to the test's transaction.

    The fixture never commits, so a task opening its own connection would
    read an empty database. Each call still gets its own session on that
    shared connection — the task rolls back a mailbox that fails, and on
    one session handed round that would take the other mailboxes with it.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory():
        # A savepoint per call, so the rollback the task performs on a
        # mailbox that failed is contained instead of discarding the seed
        # data the remaining mailboxes need.
        await db_session.begin_nested()
        yield db_session

    return {"session_factory": _factory}


async def _account(db_session, suffix: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@poll.example.com",
            account_name=f"Poll{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _mailbox(db_session, owner, *, address: str, imap: bool):
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"Casilla {address}",
            channel_type="email",
            channel_params={"email": address},
        ),
    ).perform()
    channel = await db_session.get(EmailChannel, result.inbox.channel_id)
    channel.imap_enabled = imap
    channel.imap_address = "imap.ejemplo.com"
    channel.imap_login = address
    channel.imap_password = "x"
    db_session.add(channel)
    await db_session.flush()
    return result.inbox, channel


@pytest.fixture
def polled(monkeypatch):
    """Record which mailboxes were polled, without touching a server."""
    seen: list[str] = []

    async def _fetch(session, *, channel, inbox):
        seen.append(channel.imap_login)
        return 1

    monkeypatch.setattr(
        "app.domains.email.imap_fetch.fetch_inbox_once", _fetch
    )
    return seen


async def test_polls_a_mailbox_with_imap_on(db_session, ctx, polled):
    owner = await _account(db_session, "-on")
    await _mailbox(db_session, owner, address="a@ejemplo.com", imap=True)
    await db_session.flush()

    result = await email_poll.fetch_imap_inboxes_task(ctx)
    assert polled == ["a@ejemplo.com"]
    assert result["fetched"] == 1


async def test_skips_a_mailbox_with_imap_off(db_session, ctx, polled):
    """Send-only mailboxes are a supported configuration, not a mistake."""
    owner = await _account(db_session, "-off")
    await _mailbox(db_session, owner, address="b@ejemplo.com", imap=False)
    await db_session.flush()

    await email_poll.fetch_imap_inboxes_task(ctx)
    assert polled == []


async def test_polls_every_account(db_session, ctx, polled):
    first = await _account(db_session, "-one")
    second = await _account(db_session, "-two")
    await _mailbox(db_session, first, address="uno@ejemplo.com", imap=True)
    await _mailbox(db_session, second, address="dos@ejemplo.com", imap=True)
    await db_session.flush()

    await email_poll.fetch_imap_inboxes_task(ctx)
    assert sorted(polled) == ["dos@ejemplo.com", "uno@ejemplo.com"]


async def test_an_account_with_no_mailboxes_is_a_cheap_no_op(db_session, ctx, polled):
    result = await email_poll.fetch_imap_inboxes_task(ctx)
    assert result == {"mailboxes": 0, "fetched": 0}
    assert polled == []
