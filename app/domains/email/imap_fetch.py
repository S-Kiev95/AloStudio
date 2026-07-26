"""IMAP poller — pulls UNSEEN messages from a Channel::Email and
hands each one to :func:`process_inbound_email`.

Ported from:
  reference/chatwoot/app/services/imap/base_fetch_email_service.rb
  reference/chatwoot/app/services/imap/fetch_email_service.rb
  reference/chatwoot/app/jobs/inboxes/fetch_imap_emails_job.rb

Connection model:
  * Connect via ``aioimaplib`` — async-native so we don't block the
    event loop on slow IMAP servers.
  * Login with the channel's ``imap_login`` + ``imap_password``.
  * SELECT INBOX, then SEARCH for UNSEEN to grab new mails.
  * FETCH each by UID, parse to ``EmailMessage``, hand off.
  * After successful processing, mark each fetched UID ``\\Seen`` so
    the next poll skips them. Failure mid-fetch leaves the flag clear
    so a retry picks them up.

We DON'T port Chatwoot's V2 ``\\Flagged`` workflow yet — that's an
optimization for accounts using IMAP IDLE notifications. Phase 5b
ships the simple polling path, sufficient for parity.

This module exposes :func:`fetch_inbox_once` — call it from an ARQ
periodic task (Phase 5b.5 wiring) to poll an inbox. Tests call it
directly without scheduling.
"""

from __future__ import annotations

import email
import logging
from contextlib import suppress
from email.message import EmailMessage

import aioimaplib
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.email.inbound import process_inbound_email
from app.domains.inboxes.models import (
    CHANNEL_TYPE_EMAIL,
    EmailChannel,
    Inbox,
)

log = logging.getLogger(__name__)

# Connect / login / fetch — short ceiling so a hung IMAP server can't
# starve the event loop. Rails uses 30s, we mirror.
IMAP_TIMEOUT_SECONDS = 30


def _parse_email_bytes(raw: bytes) -> EmailMessage:
    """Wrap ``email.message_from_bytes`` to return an EmailMessage.

    The default ``policy.compat32`` returns a legacy ``Message`` which
    has different ``get_content()`` semantics. We force the modern
    policy so :mod:`app.domains.email.inbound` can call ``walk()`` +
    ``get_content()`` uniformly.
    """
    return email.message_from_bytes(raw, policy=email.policy.default)


async def _connect_and_select(
    channel: EmailChannel,
) -> aioimaplib.IMAP4_SSL | aioimaplib.IMAP4:
    """Open a logged-in IMAP session selecting INBOX."""
    cls = aioimaplib.IMAP4_SSL if channel.imap_enable_ssl else aioimaplib.IMAP4
    imap = cls(host=channel.imap_address, port=channel.imap_port, timeout=IMAP_TIMEOUT_SECONDS)
    await imap.wait_hello_from_server()
    res = await imap.login(channel.imap_login, channel.imap_password)
    if res.result != "OK":
        await imap.logout()
        raise RuntimeError(
            f"IMAP login failed for channel {channel.id}: {res.lines!r}"
        )
    sel = await imap.select("INBOX")
    if sel.result != "OK":
        await imap.logout()
        raise RuntimeError(
            f"IMAP SELECT INBOX failed: {sel.lines!r}"
        )
    return imap


async def _fetch_unseen_uids(imap: aioimaplib.IMAP4) -> list[bytes]:
    """SEARCH UNSEEN -> list of UID bytes."""
    res = await imap.search("UNSEEN")
    if res.result != "OK" or not res.lines:
        return []
    # res.lines[0] is e.g. b"1 2 3" (space-separated UIDs).
    raw = res.lines[0]
    if not raw:
        return []
    return [tok for tok in raw.split() if tok]


async def _fetch_one(imap: aioimaplib.IMAP4, uid: bytes) -> EmailMessage | None:
    """FETCH (RFC822) one message by UID.

    aioimaplib returns the raw response in ``lines`` — we pluck the
    bytes payload out and parse it. Returns ``None`` on a malformed
    response (logged + skipped — the caller wants the loop to keep
    going).
    """
    res = await imap.fetch(uid.decode("ascii"), "(RFC822)")
    if res.result != "OK" or not res.lines:
        return None
    # Response shape: [b"<n> FETCH (RFC822 {<size>}", b"<bytes>", b")"]
    # The actual mail body is the second-to-last line; the last line
    # is just a closing paren.
    if len(res.lines) < 2:
        return None
    raw = res.lines[1]
    if not isinstance(raw, (bytes, bytearray)):
        return None
    try:
        return _parse_email_bytes(bytes(raw))
    except Exception:
        log.exception("email.imap.parse_failed uid=%s", uid)
        return None


async def fetch_inbox_once(
    session: AsyncSession,
    *,
    channel: EmailChannel,
    inbox: Inbox,
) -> int:
    """Run one poll cycle on the inbox.

    Returns the count of messages successfully ingested. Caller
    schedules subsequent polls — we don't loop here.

    Pre-conditions:
      * ``channel.imap_enabled`` is True.
      * ``channel.imap_address`` / ``imap_port`` / ``imap_login``
        / ``imap_password`` are set.
      * ``inbox.channel_type == 'Channel::Email'`` and points at this
        channel (caller's responsibility to pass the matching pair).

    Connection / login / fetch errors are logged but not raised — a
    flaky server shouldn't crash the worker. The caller can inspect
    the return value (0) to detect the no-progress case.
    """
    if not channel.imap_enabled:
        return 0
    if inbox.channel_type != CHANNEL_TYPE_EMAIL:
        return 0
    if not (channel.imap_address and channel.imap_port and channel.imap_login):
        return 0

    try:
        imap = await _connect_and_select(channel)
    except (RuntimeError, OSError, TimeoutError, aioimaplib.Abort) as exc:
        log.warning(
            "email.imap.connect_failed channel_id=%s error=%s",
            channel.id,
            exc,
        )
        return 0

    ingested = 0
    try:
        uids = await _fetch_unseen_uids(imap)
        for uid in uids:
            mail = await _fetch_one(imap, uid)
            if mail is None:
                continue
            try:
                msg = await process_inbound_email(
                    session, channel=channel, inbox=inbox, mail=mail
                )
            except Exception:
                log.exception(
                    "email.imap.process_failed channel_id=%s uid=%s",
                    channel.id,
                    uid,
                )
                continue
            if msg is not None:
                ingested += 1
                # Mark seen so the next poll skips this UID. We do this
                # AFTER successful processing — a crash mid-fetch leaves
                # the flag clear so the retry picks the message up.
                try:
                    await imap.store(
                        uid.decode("ascii"), "+FLAGS", "(\\Seen)"
                    )
                except Exception:
                    log.exception(
                        "email.imap.store_seen_failed channel_id=%s uid=%s",
                        channel.id,
                        uid,
                    )
    finally:
        # Best-effort logout: a dead socket must not sink an otherwise
        # successful poll.
        with suppress(Exception):
            await imap.logout()
    return ingested


async def fetch_all_email_inboxes_once(session: AsyncSession) -> int:
    """Iterate every IMAP-enabled Email channel + run one poll each.

    Mirrors ``Inboxes::FetchImapEmailInboxesJob`` — the cron entry point
    Chatwoot fires every minute. Returns the total count of messages
    ingested across every inbox.
    """
    rows = list(
        (
            await session.exec(
                select(EmailChannel, Inbox)
                .join(
                    Inbox,
                    (Inbox.channel_type == CHANNEL_TYPE_EMAIL)
                    & (Inbox.channel_id == EmailChannel.id),
                )
                .where(EmailChannel.imap_enabled.is_(True))
            )
        ).all()
    )
    total = 0
    for channel, inbox in rows:
        total += await fetch_inbox_once(
            session, channel=channel, inbox=inbox
        )
    return total


__all__ = ["fetch_all_email_inboxes_once", "fetch_inbox_once"]
