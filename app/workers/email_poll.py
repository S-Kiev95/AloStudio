"""ARQ task that polls every IMAP-enabled mailbox once.

``fetch_inbox_once`` shipped tested but unscheduled — the note in
:mod:`app.domains.email.imap_fetch` deferred the wiring — so inbound mail
only arrived if somebody ran it by hand. This is that wiring.

One task for all mailboxes rather than one per mailbox: the set changes
whenever an inbox is added, and a cron built from it at worker start would
go stale until the next restart. Reading the list each run means a mailbox
configured a minute ago is polled on the next tick.

Each mailbox is isolated. A server that is down, a password that was
rotated, a mailbox with thousands of unread — none of them may stop the
others from being polled, so every one gets its own try/except and its own
session.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

log = logging.getLogger(__name__)


async def fetch_imap_inboxes_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """Poll every mailbox with IMAP switched on. Never raises."""
    from app.core.db import get_session_factory
    from app.domains.email.imap_fetch import fetch_inbox_once
    from app.domains.inboxes.models import (
        CHANNEL_TYPE_EMAIL,
        EmailChannel,
        Inbox,
    )

    # Three ways to get a session, most specific first. ``session_factory``
    # is the seam a caller uses to bind this to a transaction it controls —
    # a test wraps everything in one that never commits, so a task that
    # only ever opened its own connection could not be driven at all.
    engine = ctx.get("engine") if isinstance(ctx, dict) else None
    factory = (ctx.get("session_factory") if isinstance(ctx, dict) else None) or (
        async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        if engine is not None
        else get_session_factory()
    )

    async with factory() as session:
        pairs = list(
            (
                await session.exec(
                    select(Inbox, EmailChannel)
                    .join(EmailChannel, EmailChannel.id == Inbox.channel_id)
                    .where(
                        Inbox.channel_type == CHANNEL_TYPE_EMAIL,
                        EmailChannel.imap_enabled.is_(True),
                    )
                )
            ).all()
        )

    if not pairs:
        return {"mailboxes": 0, "fetched": 0}

    fetched = 0
    failed = 0
    for inbox, channel in pairs:
        # A fresh session per mailbox: one that dies mid-poll leaves a
        # transaction the next mailbox would inherit.
        async with factory() as session:
            try:
                fetched += await fetch_inbox_once(
                    session, channel=channel, inbox=inbox
                )
                await session.commit()
            except Exception:
                failed += 1
                await session.rollback()
                log.exception(
                    "email.poll.failed inbox_id=%s address=%s",
                    inbox.id,
                    channel.imap_address,
                )

    log.info(
        "email.poll.done mailboxes=%s fetched=%s failed=%s",
        len(pairs),
        fetched,
        failed,
    )
    return {"mailboxes": len(pairs), "fetched": fetched, "failed": failed}


__all__ = ["fetch_imap_inboxes_task"]
