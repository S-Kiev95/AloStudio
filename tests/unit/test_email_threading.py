"""Unit tests for ``app.domains.email.threading``.

Pin the RFC-2822 Message-ID extraction so a malformed header can't
break the IMAP ingest path. The DB-touching ``find_conversation
_by_thread`` is exercised via integration tests once 5b.4 lands;
here we cover the pure-parsing surface.
"""

from __future__ import annotations

import pytest

from app.domains.email.threading import (
    ThreadingHeaders,
    extract_message_ids,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# extract_message_ids
# ---------------------------------------------------------------------------
def test_extracts_single_bracketed_mid() -> None:
    assert extract_message_ids("<abc@example.com>") == ["abc@example.com"]


def test_extracts_chain_of_mids() -> None:
    raw = "<a@example.com> <b@example.com> <c@example.com>"
    assert extract_message_ids(raw) == [
        "a@example.com",
        "b@example.com",
        "c@example.com",
    ]


def test_dedupes_repeated_mids() -> None:
    """Some clients echo the same Message-ID in In-Reply-To AND first
    of References. We dedupe so the DB lookup does one IN-clause hit
    per real id."""
    raw = "<a@example.com> <a@example.com> <b@example.com>"
    assert extract_message_ids(raw) == [
        "a@example.com",
        "b@example.com",
    ]


def test_handles_none_and_blank() -> None:
    assert extract_message_ids(None) == []
    assert extract_message_ids("") == []
    assert extract_message_ids("   \t\n") == []


def test_accepts_unbracketed_mids() -> None:
    """Old servers ship ``Message-ID: id@host`` without brackets.
    RFC-2822 forbids it but a parser that rejects them loses real
    threads."""
    assert extract_message_ids("legacy@example.com") == ["legacy@example.com"]


def test_skips_garbage_between_mids() -> None:
    raw = "  blah blah <a@example.com>  ,, ; <b@example.com>  trailing  "
    assert extract_message_ids(raw) == [
        "a@example.com",
        "b@example.com",
    ]


def test_skips_strings_without_at_sign() -> None:
    assert extract_message_ids("<no-at-symbol>") == []
    assert extract_message_ids("just-text") == []


def test_handles_dots_and_hyphens_in_addr_spec() -> None:
    raw = "<20240429.123-thread@mail.example.co.uk>"
    assert extract_message_ids(raw) == ["20240429.123-thread@mail.example.co.uk"]


# ---------------------------------------------------------------------------
# ThreadingHeaders.candidate_ids
# ---------------------------------------------------------------------------
def test_candidate_ids_orders_in_reply_to_first() -> None:
    """Mirror Rails' lookup order: parent (In-Reply-To) before chain
    (References). The DB query stops at the first match, so order
    matters when both columns reference the same conversation but
    different messages."""
    h = ThreadingHeaders(
        in_reply_to="<reply-to@example.com>",
        references="<root@example.com> <reply-to@example.com>",
    )
    assert h.candidate_ids() == [
        "reply-to@example.com",
        "root@example.com",
    ]


def test_candidate_ids_dedupe_across_headers() -> None:
    """Many clients put the parent's Message-ID in BOTH In-Reply-To
    and References — we want to hit the DB once."""
    h = ThreadingHeaders(
        in_reply_to="<a@example.com>",
        references="<a@example.com>",
    )
    assert h.candidate_ids() == ["a@example.com"]


def test_candidate_ids_empty_when_no_headers() -> None:
    h = ThreadingHeaders()
    assert h.candidate_ids() == []
