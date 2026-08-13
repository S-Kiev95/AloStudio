"""Wiring between an incoming comment and the reply that answers it.

Split from :mod:`app.domains.instagram.autoreply` (which only decides) so
the decision can be tested without a queue, and from the worker task so
the sending can be retried independently of the webhook that triggered it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.inboxes.models import InstagramChannel
from app.domains.instagram.autoreply import decide_reply
from app.domains.instagram.models import (
    InstagramChannelSetting,
    InstagramComment,
)

log = logging.getLogger(__name__)


async def _setting_for(
    session: AsyncSession, *, channel_instagram_id: int
) -> InstagramChannelSetting | None:
    return (
        await session.exec(
            select(InstagramChannelSetting).where(
                InstagramChannelSetting.channel_instagram_id
                == channel_instagram_id
            )
        )
    ).first()


async def maybe_enqueue_autoreply(
    session: AsyncSession,
    *,
    comment: InstagramComment,
    channel: InstagramChannel,
) -> bool:
    """Decide, and queue the send when the answer is yes.

    Returns whether a job was queued. Deciding here rather than inside the
    job keeps the expensive path (a Graph call) off the webhook for every
    comment that will not be answered — which is most of them.
    """
    setting = await _setting_for(
        session, channel_instagram_id=channel.id
    )
    decision = await decide_reply(
        session,
        comment=comment,
        setting=setting,
        # Our own replies are authored by the IG account itself; this is
        # what the loop guard compares against.
        our_ig_user_id=channel.instagram_id,
    )
    if not decision.should_reply:
        # Debug, not info: on a busy account most comments end here and
        # this would otherwise drown the log.
        log.debug(
            "instagram.autoreply.skipped comment=%s reason=%s",
            comment.ig_comment_id,
            decision.reason,
        )
        return False

    # Claim the comment *before* queueing. If the send fails the comment
    # stays claimed and is not retried automatically — a silent miss is
    # recoverable by a human, a double public reply is not.
    comment.auto_replied_at = datetime.now(UTC)
    session.add(comment)
    await session.flush()

    from app.workers.instagram_autoreply import enqueue_autoreply

    await enqueue_autoreply(
        comment_id=comment.id,  # type: ignore[arg-type]
        text=decision.text or "",
    )
    log.info(
        "instagram.autoreply.queued comment=%s reason=%s distance=%s",
        comment.ig_comment_id,
        decision.reason,
        decision.distance,
    )
    return True


__all__ = ["maybe_enqueue_autoreply"]
