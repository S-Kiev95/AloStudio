"""Bounding the first poll to mail that arrived after connecting.

``SEARCH UNSEEN`` answers with a mailbox's whole unread backlog.
Connecting a real Gmail account to staging turned 114 newsletters into
114 conversations in three minutes — on a desk that has been running for
years it is thousands, each one something a person has to close.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.domains.email.imap_fetch import _fetch_unseen_uids

pytestmark = pytest.mark.unit


class _Imap:
    """Records the search criteria it was handed."""

    def __init__(self, uids: bytes = b"1 2 3"):
        self.criteria: str | None = None
        self._uids = uids

    async def search(self, criteria: str):
        self.criteria = criteria
        return SimpleNamespace(result="OK", lines=[self._uids])


async def test_an_unbounded_mailbox_searches_everything_unread():
    """Null means no bound — what every mailbox connected before had."""
    imap = _Imap()
    await _fetch_unseen_uids(imap, since=None)
    assert imap.criteria == "UNSEEN"


async def test_a_bounded_mailbox_asks_only_for_recent_mail():
    imap = _Imap()
    await _fetch_unseen_uids(imap, since=datetime(2026, 8, 18, tzinfo=UTC))
    assert imap.criteria == "UNSEEN SINCE 18-Aug-2026"


async def test_the_date_is_in_the_format_imap_understands():
    # IMAP wants dd-Mon-yyyy with an English month; a locale-formatted
    # date is rejected by the server, which would read as "no new mail".
    imap = _Imap()
    await _fetch_unseen_uids(imap, since=datetime(2026, 1, 5, tzinfo=UTC))
    assert imap.criteria == "UNSEEN SINCE 05-Jan-2026"


async def test_it_still_returns_the_uids():
    imap = _Imap(b"7 8")
    uids = await _fetch_unseen_uids(imap, since=datetime(2026, 8, 18, tzinfo=UTC))
    assert uids == [b"7", b"8"]
