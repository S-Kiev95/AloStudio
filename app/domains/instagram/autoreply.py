"""Decide whether — and what — to auto-reply to an Instagram comment.

Pure decision logic, split from the sending so the rules can be tested
without touching Meta. :func:`decide_reply` answers "should we say
something, what, and where", and the caller does the posting.

The guards matter more than the matching. A public reply is a comment on
the brand's own post, so the failure modes are visible to the audience:
answering our own reply in a loop, answering the same person twice after a
webhook redelivery, or confidently answering the wrong question.

Rules live on the publication (see
:mod:`app.domains.instagram.post_autoreply_models`) and are tried
most-specific first: keyword, then semantic, then catch-all.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.llm import embed_text, embedding_search_enabled
from app.domains.instagram.autoreply_models import (
    DEFAULT_MATCH_MAX_DISTANCE,
    InstagramCommentReply,
)
from app.domains.instagram.models import InstagramComment, InstagramPost
from app.domains.instagram.post_autoreply_models import (
    DELIVERY_PUBLIC,
    MATCH_ALL,
    MATCH_KEYWORD,
    MATCH_PRIORITY,
    MATCH_SEMANTIC,
    InstagramPostAutoreply,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplyDecision:
    """What to do with one comment. ``text`` None means stay quiet."""

    text: str | None = None
    reason: str = "no_match"
    delivery: str = DELIVERY_PUBLIC
    rule_id: int | None = None
    distance: float | None = None

    @property
    def should_reply(self) -> bool:
        return bool(self.text)


def _fold(text: str) -> str:
    """Lowercase and strip accents.

    Someone typing "INFO", "info" or "línk" should trigger a rule written
    plainly — a keyword mechanic that only fires on an exact spelling would
    miss most of the audience it is aimed at.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _keyword_hit(rule: InstagramPostAutoreply, comment_text: str) -> bool:
    folded = _fold(comment_text)
    for raw in (rule.keywords or "").split(","):
        word = _fold(raw.strip())
        if word and word in folded:
            return True
    return False


async def _semantic_match(
    session: AsyncSession,
    *,
    account_id: int,
    text: str,
    max_distance: float,
) -> tuple[str | None, str, float | None]:
    """``(reply, reason, distance)`` from the account's answer library."""
    if not embedding_search_enabled():
        return None, "embeddings_disabled", None
    try:
        vector = await embed_text(text)
    except Exception:
        # Embedding is a network call; if it fails we simply do not answer.
        # Silence is always a safe outcome here.
        log.exception("instagram.autoreply.embed_failed account_id=%s", account_id)
        return None, "embed_failed", None

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
        return None, "no_prepared_answers", None

    candidate, dist = row
    if dist is None or float(dist) > max_distance:
        # A near-miss is not an answer. Leaving it for a person costs a
        # minute; answering the wrong question costs it in public.
        return None, "below_threshold", (float(dist) if dist is not None else None)
    return candidate.reply, "semantic_match", float(dist)


async def _rules_for_post(
    session: AsyncSession, *, post_id: int
) -> list[InstagramPostAutoreply]:
    rules = list(
        (
            await session.exec(
                select(InstagramPostAutoreply).where(
                    InstagramPostAutoreply.post_id == post_id,
                    InstagramPostAutoreply.enabled.is_(True),
                )
            )
        ).all()
    )
    # Most specific first, so a catch-all cannot swallow a keyword rule.
    rules.sort(key=lambda r: MATCH_PRIORITY.get(r.match_type, 99))
    return rules


async def decide_reply(
    session: AsyncSession,
    *,
    comment: InstagramComment,
    post: InstagramPost | None,
    our_ig_user_id: str | None,
) -> ReplyDecision:
    """Whether to answer ``comment``, with what, and where.

    ``our_ig_user_id`` is the id our own replies are authored by — the
    anti-loop guard depends on it, so when it is unknown the safe move is
    to stay quiet rather than risk talking to ourselves.
    """
    if post is None:
        # The comment arrived on media we do not have a post row for
        # (published outside AloStudio, for instance).
        return ReplyDecision(reason="unknown_post")

    # --- guards -------------------------------------------------------------
    if comment.auto_replied_at is not None:
        # Meta redelivers webhooks on failure and the sync re-reads existing
        # threads; without this the same person is answered repeatedly.
        return ReplyDecision(reason="already_replied")

    text = (comment.text or "").strip()
    if not text:
        # Sticker/emoji-only comments carry nothing to match on.
        return ReplyDecision(reason="empty_comment")

    if comment.parent_comment_id:
        # Only top-level comments. Answering inside a reply thread turns a
        # conversation between two people into a three-way with a bot.
        return ReplyDecision(reason="is_a_reply")

    if our_ig_user_id is None:
        return ReplyDecision(reason="unknown_own_id")

    if comment.from_id and str(comment.from_id) == str(our_ig_user_id):
        # The loop guard. Our public reply is itself a comment that fires
        # the same webhook; without this the account answers itself.
        return ReplyDecision(reason="own_comment")

    if comment.hidden:
        return ReplyDecision(reason="hidden")

    # --- rules --------------------------------------------------------------
    rules = await _rules_for_post(session, post_id=post.id)
    if not rules:
        return ReplyDecision(reason="no_rules")

    for rule in rules:
        if rule.match_type == MATCH_KEYWORD:
            if not _keyword_hit(rule, text):
                continue
            body = (rule.reply_text or "").strip()
            if not body:
                continue
            return ReplyDecision(
                text=body,
                reason="keyword",
                delivery=rule.delivery,
                rule_id=rule.id,
            )

        if rule.match_type == MATCH_SEMANTIC:
            body, reason, distance = await _semantic_match(
                session,
                account_id=comment.account_id,
                text=text,
                max_distance=DEFAULT_MATCH_MAX_DISTANCE,
            )
            if body is None:
                # Fall through to a catch-all rule if one exists — a
                # library miss should not block a generic answer.
                log.debug(
                    "instagram.autoreply.semantic_miss comment=%s reason=%s",
                    comment.ig_comment_id,
                    reason,
                )
                continue
            return ReplyDecision(
                text=body,
                reason=reason,
                delivery=rule.delivery,
                rule_id=rule.id,
                distance=distance,
            )

        if rule.match_type == MATCH_ALL:
            body = (rule.reply_text or "").strip()
            if not body:
                continue
            return ReplyDecision(
                text=body,
                reason="catch_all",
                delivery=rule.delivery,
                rule_id=rule.id,
            )

    return ReplyDecision(reason="no_match")


__all__ = ["ReplyDecision", "decide_reply"]
