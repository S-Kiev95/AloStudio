"""Decide whether — and what — to auto-reply to an Instagram comment.

Pure decision logic, split from the sending so the rules can be tested
without touching Meta. :func:`decide_reply` answers "should we say
something, and what", and the caller does the posting.

The guards matter more than the matching here. A reply is itself a public
comment on the brand's own post, so the failure modes are visible to the
audience: answering our own reply in a loop, answering the same person
twice after a webhook redelivery, or confidently answering the wrong
question.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.llm import embed_text, embedding_search_enabled
from app.domains.instagram.autoreply_models import (
    AUTOREPLY_FIXED,
    AUTOREPLY_SEMANTIC,
    InstagramCommentReply,
)
from app.domains.instagram.models import (
    InstagramChannelSetting,
    InstagramComment,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplyDecision:
    """What to do with one comment. ``text`` None means stay quiet."""

    text: str | None = None
    reason: str = "no_match"
    # Which prepared answer matched, for auditing why a reply was sent.
    reply_id: int | None = None
    distance: float | None = None

    @property
    def should_reply(self) -> bool:
        return bool(self.text)


async def _semantic_match(
    session: AsyncSession,
    *,
    account_id: int,
    text: str,
    max_distance: float,
) -> ReplyDecision:
    """Nearest prepared answer by meaning, if it clears the threshold."""
    if not embedding_search_enabled():
        return ReplyDecision(reason="embeddings_disabled")

    try:
        vector = await embed_text(text)
    except Exception:
        # Embedding is a network call; if it fails we simply do not answer.
        # Silence is always a safe outcome here.
        log.exception("instagram.autoreply.embed_failed account_id=%s", account_id)
        return ReplyDecision(reason="embed_failed")

    distance = InstagramCommentReply.embedding.cosine_distance(vector)
    row = (
        await session.exec(
            select(InstagramCommentReply, distance.label("distance"))
            .where(
                InstagramCommentReply.account_id == account_id,
                InstagramCommentReply.enabled.is_(True),
                InstagramCommentReply.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(1)
        )
    ).first()
    if row is None:
        return ReplyDecision(reason="no_prepared_answers")

    candidate, dist = row
    if dist is None or float(dist) > max_distance:
        # The whole point of the threshold: a near-miss is not an answer.
        # Leaving it for a person costs a minute; answering the wrong
        # question costs it in public.
        return ReplyDecision(
            reason="below_threshold", distance=float(dist) if dist else None
        )
    return ReplyDecision(
        text=candidate.reply,
        reason="semantic_match",
        reply_id=candidate.id,
        distance=float(dist),
    )


async def decide_reply(
    session: AsyncSession,
    *,
    comment: InstagramComment,
    setting: InstagramChannelSetting | None,
    our_ig_user_id: str | None,
) -> ReplyDecision:
    """Whether to answer ``comment``, and with what.

    ``our_ig_user_id`` is the Instagram-scoped id our own replies are
    authored by — the anti-loop guard depends on it, so when it is unknown
    the safe move is to stay quiet rather than risk talking to ourselves.
    """
    if setting is None:
        return ReplyDecision(reason="no_settings")

    mode = (setting.comment_autoreply_mode or "off").lower()
    if mode not in (AUTOREPLY_FIXED, AUTOREPLY_SEMANTIC):
        return ReplyDecision(reason="disabled")

    # --- guards -------------------------------------------------------------
    if comment.auto_replied_at is not None:
        # Meta redelivers webhooks on failure and the sync re-reads existing
        # threads; without this the same person is answered repeatedly.
        return ReplyDecision(reason="already_replied")

    if not (comment.text or "").strip():
        # Sticker/emoji-only comments carry nothing to match on.
        return ReplyDecision(reason="empty_comment")

    if comment.parent_comment_id:
        # Only top-level comments. Answering inside a reply thread turns a
        # conversation between two people into a three-way with a bot.
        return ReplyDecision(reason="is_a_reply")

    if our_ig_user_id is None:
        return ReplyDecision(reason="unknown_own_id")

    if comment.from_id and str(comment.from_id) == str(our_ig_user_id):
        # The loop guard. Our reply is itself a comment that fires the same
        # webhook; without this the account answers itself indefinitely.
        return ReplyDecision(reason="own_comment")

    if comment.hidden:
        return ReplyDecision(reason="hidden")

    # --- mode ---------------------------------------------------------------
    if mode == AUTOREPLY_FIXED:
        text = (setting.comment_autoreply_text or "").strip()
        if not text:
            return ReplyDecision(reason="fixed_text_missing")
        return ReplyDecision(text=text, reason="fixed")

    return await _semantic_match(
        session,
        account_id=comment.account_id,
        text=comment.text or "",
        max_distance=setting.comment_autoreply_max_distance or 0.35,
    )


__all__ = ["ReplyDecision", "decide_reply"]
