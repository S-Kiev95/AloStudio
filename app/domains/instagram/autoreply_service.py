"""Wiring between an incoming comment and the reply that answers it.

Split from :mod:`app.domains.instagram.autoreply` (which only decides) so
the rules can be tested without a queue, and from the worker task so the
sending can be retried independently of the webhook that triggered it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Conversation, Message
from app.domains.inboxes.models import (
    CHANNEL_TYPE_INSTAGRAM,
    Inbox,
    InstagramChannel,
)
from app.domains.instagram.autoreply import decide_reply
from app.domains.instagram.models import InstagramComment, InstagramPost

log = logging.getLogger(__name__)


async def _post_for_comment(
    session: AsyncSession, *, comment: InstagramComment
) -> InstagramPost | None:
    """The publication a comment landed on, matched on Meta's media id."""
    if not comment.ig_media_id:
        return None
    return (
        await session.exec(
            select(InstagramPost).where(
                InstagramPost.account_id == comment.account_id,
                InstagramPost.ig_media_id == comment.ig_media_id,
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
    job keeps the Graph call off the webhook for every comment that will
    not be answered — which is most of them.
    """
    post = await _post_for_comment(session, comment=comment)
    decision = await decide_reply(
        session,
        comment=comment,
        post=post,
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
        delivery=decision.delivery,
    )
    log.info(
        "instagram.autoreply.queued comment=%s reason=%s delivery=%s distance=%s",
        comment.ig_comment_id,
        decision.reason,
        decision.delivery,
        decision.distance,
    )
    return True


# ---------------------------------------------------------------------------
# Recording the reply we sent
# ---------------------------------------------------------------------------
async def _inbox_for_channel(
    session: AsyncSession, *, channel: InstagramChannel
) -> Inbox | None:
    return (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_INSTAGRAM,
                Inbox.channel_id == channel.id,
            )
        )
    ).first()


async def record_private_reply(
    session: AsyncSession,
    *,
    comment: InstagramComment,
    channel: InstagramChannel,
    text: str,
    recipient_igsid: str,
    message_id: str | None,
) -> Conversation | None:
    """Land the DM we just sent in the agent inbox.

    Without this the reply exists only on Instagram: if the person answers,
    the team sees a bare reply with nothing above it, and nobody can tell
    how many people the link went out to.

    Keyed on the IGSID Meta returns rather than the comment's ``from.id``
    so it lands on the same contact a later inbound DM resolves to — the
    two ids are not interchangeable across login types.

    Best-effort by design: the reply is already delivered, so a failure
    here must not surface as a failed send.
    """
    from app.domains.contacts.service import ContactInboxBuilder
    from app.domains.conversations.service import (
        MessageBuilderParams,
        create_message,
    )
    from app.domains.instagram.incoming import (
        find_or_create_ig_contact,
        find_or_create_ig_conversation,
    )

    inbox = await _inbox_for_channel(session, channel=channel)
    if inbox is None:
        log.warning(
            "instagram.autoreply.record_skipped reason=no_inbox channel=%s",
            channel.id,
        )
        return None

    # The echo Meta may deliver for our own send carries this same mid, and
    # the inbound path skips a mid it already holds — so writing it here is
    # what stops the reply appearing twice.
    if message_id:
        already = (
            await session.exec(
                select(Message.id).where(
                    Message.account_id == channel.account_id,
                    Message.source_id == message_id,
                )
            )
        ).first()
        if already is not None:
            return None

    contact = await find_or_create_ig_contact(
        session, account_id=channel.account_id, igsid=recipient_igsid
    )
    contact_inbox = await ContactInboxBuilder(
        session=session,
        contact=contact,
        inbox=inbox,
        source_id=recipient_igsid,
    ).perform()
    conversation = await find_or_create_ig_conversation(
        session, contact_inbox=contact_inbox
    )
    await create_message(
        session,
        conversation=conversation,
        params=MessageBuilderParams(
            content=text,
            message_type="outgoing",
            source_id=message_id,
            # No sender_id: nobody on the team wrote this. The marker is
            # what lets the UI and reports tell it apart from an agent's
            # reply instead of crediting a human with it.
            content_attributes={
                "automation": "instagram_comment_autoreply",
                "instagram_comment_id": comment.ig_comment_id,
            },
        ),
        user_id=None,
    )

    # Back-link so the comment in the moderation view points at the thread
    # it opened.
    if conversation.id is not None:
        comment.conversation_id = conversation.id
        session.add(comment)
    await session.flush()
    log.info(
        "instagram.autoreply.recorded comment=%s conversation=%s mid=%s",
        comment.ig_comment_id,
        conversation.id,
        message_id,
    )
    return conversation


__all__ = ["maybe_enqueue_autoreply", "record_private_reply"]
