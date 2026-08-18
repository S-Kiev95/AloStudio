"""One unreachable mailbox must not stop the rest being polled.

A server that is down or a password that was rotated is the normal
failure here, not the exceptional one. Driven with a stub session because
what is under test is the loop and its bookkeeping, not the query.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.workers import email_poll

pytestmark = pytest.mark.unit


def _mailbox(login: str):
    inbox = SimpleNamespace(id=hash(login) % 1000, channel_id=1)
    channel = SimpleNamespace(imap_login=login, imap_address="imap.x.com")
    return inbox, channel


class _StubSession:
    """Just enough session for the task: one query, then commit/rollback."""

    def __init__(self, rows):
        self._rows = rows
        self.committed = 0
        self.rolled_back = 0

    async def exec(self, _stmt):
        return SimpleNamespace(all=lambda: self._rows)

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        self.rolled_back += 1


@pytest.fixture
def drive(monkeypatch):
    """Run the task over ``logins``, failing the ones named in ``broken``."""

    def _run(logins: list[str], broken: set[str]):
        rows = [_mailbox(login) for login in logins]
        session = _StubSession(rows)

        @asynccontextmanager
        async def _factory():
            yield session

        reached: list[str] = []

        async def _fetch(_session, *, channel, inbox):
            reached.append(channel.imap_login)
            if channel.imap_login in broken:
                raise OSError("connection refused")
            return 2

        monkeypatch.setattr(
            "app.domains.email.imap_fetch.fetch_inbox_once", _fetch
        )
        return session, reached, _factory

    return _run


async def test_a_dead_mailbox_does_not_stop_the_next_one(drive):
    _s, reached, factory = drive(["rota@x.com", "sana@x.com"], {"rota@x.com"})
    result = await email_poll.fetch_imap_inboxes_task(
        {"session_factory": factory}
    )
    assert reached == ["rota@x.com", "sana@x.com"]
    assert result["failed"] == 1
    assert result["fetched"] == 2


async def test_the_failure_is_counted_not_swallowed(drive):
    _s, _r, factory = drive(["a@x.com", "b@x.com"], {"a@x.com", "b@x.com"})
    result = await email_poll.fetch_imap_inboxes_task(
        {"session_factory": factory}
    )
    assert result == {"mailboxes": 2, "fetched": 0, "failed": 2}


async def test_a_failed_mailbox_rolls_back_its_own_work(drive):
    session, _r, factory = drive(["rota@x.com", "sana@x.com"], {"rota@x.com"})
    await email_poll.fetch_imap_inboxes_task({"session_factory": factory})
    # The one that worked commits; the one that failed unwinds.
    assert session.committed == 1
    assert session.rolled_back == 1


async def test_every_mailbox_succeeding_commits_each(drive):
    session, _r, factory = drive(["a@x.com", "b@x.com"], set())
    result = await email_poll.fetch_imap_inboxes_task(
        {"session_factory": factory}
    )
    assert session.committed == 2
    assert session.rolled_back == 0
    assert result["fetched"] == 4
