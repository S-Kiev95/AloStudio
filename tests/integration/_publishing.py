"""Shared helpers for the publishing tests."""

from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.inboxes.models import Inbox
from app.domains.publishing import service as svc
from app.domains.publishing.models import PublishingChannel


async def channel_of(session: AsyncSession, inbox: Inbox) -> PublishingChannel:
    """The publishing channel an inbox gets (as listing the channels does)."""
    await svc.sync_inbox_channels(session, account_id=inbox.account_id)
    return (
        await session.exec(
            select(PublishingChannel).where(PublishingChannel.inbox_id == inbox.id)
        )
    ).one()


async def channel_id_of(session: AsyncSession, inbox: Inbox) -> int:
    channel = await channel_of(session, inbox)
    assert channel.id is not None
    return channel.id
