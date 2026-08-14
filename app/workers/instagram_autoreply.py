"""ARQ task that posts an automatic reply to an Instagram comment.

Separate from the webhook so Meta gets its 200 immediately — a slow
webhook is retried by Meta, and a retried comment delivery would mean a
second public reply.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from app.domains.inboxes.models import InstagramChannel
    from app.domains.instagram.models import InstagramComment
    from app.domains.instagram.sender import PrivateReplyResult

log = logging.getLogger(__name__)


async def enqueue_autoreply(
    *, comment_id: int, text: str, delivery: str = "public"
) -> None:
    """Queue the reply. Falls back to sending inline with no worker.

    Mirrors ``instagram.enqueue_publish``: an environment without a worker
    (local dev) still behaves correctly, just synchronously.
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    try:
        pool = await create_pool(
            RedisSettings.from_dsn(get_settings().arq_redis_url)
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "instagram.autoreply.no_pool comment_id=%s err=%s — running inline",
            comment_id,
            exc,
        )
        await send_comment_autoreply_task({}, comment_id, text, delivery)
        return
    await pool.enqueue_job(
        "send_comment_autoreply_task", comment_id, text, delivery
    )


async def send_comment_autoreply_task(
    ctx: dict[str, Any],
    comment_id: int,
    text: str,
    delivery: str = "public",
) -> dict[str, Any]:
    """Post ``text`` as a reply to ``comment_id``.

    The comment was already marked replied by the caller, so a failure here
    leaves it unanswered rather than answered twice. That asymmetry is
    deliberate: a human can still answer a missed comment, but a duplicate
    reply is public and cannot be taken back cleanly.
    """
    from sqlmodel import select

    from app.core.db import get_session_factory
    from app.domains.inboxes.models import InstagramChannel
    from app.domains.instagram.comments_client import create_reply
    from app.domains.instagram.graph import graph_host, host_for_login_type
    from app.domains.instagram.models import (
        InstagramChannelSetting,
        InstagramComment,
    )
    from app.domains.instagram.post_autoreply_models import DELIVERY_DM
    from app.domains.instagram.sender import send_private_reply_instagram

    engine = ctx.get("engine") if isinstance(ctx, dict) else None
    factory = (
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
        comment = await session.get(InstagramComment, comment_id)
        if comment is None:
            return {"sent": False, "reason": "comment_gone"}
        channel = await session.get(
            InstagramChannel, comment.channel_instagram_id
        )
        if channel is None:
            return {"sent": False, "reason": "channel_gone"}
        setting = (
            await session.exec(
                select(InstagramChannelSetting).where(
                    InstagramChannelSetting.channel_instagram_id == channel.id
                )
            )
        ).first()

        # Facebook Login and Instagram Login publish through different Graph
        # hosts; the clients read the host from a task-local var.
        recorded: int | None = None
        with graph_host(
            host_for_login_type(setting.login_type if setting else "facebook")
        ):
            if delivery == DELIVERY_DM:
                # Private reply: the link lands in the person's inbox and
                # opens a real conversation, instead of being published
                # under the post for everyone to take.
                sent = await send_private_reply_instagram(
                    channel=channel,
                    ig_comment_id=comment.ig_comment_id,
                    text=text,
                )
                ok = sent.ok
                if ok:
                    recorded = await _record(
                        session,
                        comment=comment,
                        channel=channel,
                        text=text,
                        sent=sent,
                    )
            else:
                result = await create_reply(
                    channel,
                    ig_comment_id=comment.ig_comment_id,
                    message=text,
                )
                ok = bool(getattr(result, "ok", result))
        # The public branch writes nothing, but the DM branch does — and
        # the session is this task's own, so nothing else will commit it.
        await session.commit()
    log.info(
        "instagram.autoreply.sent comment=%s delivery=%s ok=%s conversation=%s",
        comment_id,
        delivery,
        ok,
        recorded,
    )
    return {"sent": ok, "comment_id": comment_id, "conversation_id": recorded}


async def _record(
    session: AsyncSession,
    *,
    comment: InstagramComment,
    channel: InstagramChannel,
    text: str,
    sent: PrivateReplyResult,
) -> int | None:
    """File the sent DM in the inbox, without letting that failure
    masquerade as a failed send — the reply is already delivered."""
    from app.domains.instagram.autoreply_service import record_private_reply

    if not sent.recipient_igsid:
        # Meta accepted the send but named nobody, so there is no contact
        # to file it under.
        log.warning(
            "instagram.autoreply.no_recipient_id comment=%s", comment.id
        )
        return None

    try:
        conversation = await record_private_reply(
            session,
            comment=comment,
            channel=channel,
            text=text,
            recipient_igsid=sent.recipient_igsid,
            message_id=sent.message_id,
        )
    except Exception:
        log.exception(
            "instagram.autoreply.record_failed comment=%s", comment.id
        )
        await session.rollback()
        return None
    return conversation.id if conversation is not None else None


__all__ = ["enqueue_autoreply", "send_comment_autoreply_task"]
