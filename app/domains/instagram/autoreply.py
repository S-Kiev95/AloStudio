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

from app.core.config import get_settings
from app.core.embeddings import (
    MODEL_GEMMA,
    MODEL_OPENAI,
    TASK_CLASSIFICATION,
    account_read_model,
    embed_gemma_one,
    gemma_enabled,
)
from app.core.llm import embed_text, embedding_search_enabled
from app.domains.instagram.autoreply_models import (
    DEFAULT_MATCH_MAX_DISTANCE,
    DEFAULT_MATCH_MAX_DISTANCE_GEMMA,
    InstagramCommentReply,
    InstagramPostReplyPick,
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


def _model_enabled(model: str) -> bool:
    if model == MODEL_GEMMA:
        return gemma_enabled()
    return embedding_search_enabled()


async def _embed_comment(model: str, text: str) -> list[float]:
    if model == MODEL_GEMMA:
        # Same prefix the triggers were embedded with: comparing a comment
        # to an example question is a symmetric task.
        return await embed_gemma_one(text, task=TASK_CLASSIFICATION)
    return await embed_text(text)


def _max_distance_for(rule: InstagramPostAutoreply, model: str) -> float:
    """The rule's threshold on ``model``'s scale.

    Null on the rule follows the installation default, so a rule nobody
    tuned tracks the tuned value rather than freezing whatever it was the
    day it was written. Each model has its own column: an OpenAI value read
    as a local-model one would answer every comment."""
    if model == MODEL_GEMMA:
        return rule.max_distance_gemma or DEFAULT_MATCH_MAX_DISTANCE_GEMMA
    return rule.max_distance or DEFAULT_MATCH_MAX_DISTANCE


# (reply, reason, distance, id of the closest answer)
MatchResult = tuple[str | None, str, float | None, int | None]


async def _semantic_match(
    session: AsyncSession,
    *,
    account_id: int,
    post_id: int,
    text: str,
    max_distance: float,
    model: str = MODEL_OPENAI,
    log_misses: bool = True,
) -> MatchResult:
    """``(reply, reason, distance, answer_id)`` from the answers this post
    offers, matched with ``model``'s vectors.

    Those are the ones picked for the publication, or the whole library
    when it has picked none — absence means "everything", so similarity
    matching works before anyone curates it.
    """
    if not _model_enabled(model):
        return None, "embeddings_disabled", None, None
    try:
        vector = await _embed_comment(model, text)
    except Exception:
        # Embedding is a network call; if it fails we simply do not answer.
        # Silence is always a safe outcome here.
        log.exception(
            "instagram.autoreply.embed_failed account_id=%s model=%s", account_id, model
        )
        return None, "embed_failed", None, None

    picked = list(
        (
            await session.exec(
                select(InstagramPostReplyPick.comment_reply_id).where(
                    InstagramPostReplyPick.post_id == post_id
                )
            )
        ).all()
    )

    column = (
        InstagramCommentReply.embedding_gemma
        if model == MODEL_GEMMA
        else InstagramCommentReply.embedding
    )
    distance = column.cosine_distance(vector)
    query = select(InstagramCommentReply, distance.label("distance")).where(
        InstagramCommentReply.account_id == account_id,
        InstagramCommentReply.enabled.is_(True),
        column.is_not(None),
    )
    if picked:
        query = query.where(InstagramCommentReply.id.in_(picked))
    row = (await session.exec(query.order_by(distance).limit(1))).first()
    if row is None:
        return None, "no_prepared_answers", None, None

    candidate, dist = row
    if dist is None or float(dist) > max_distance:
        # A near-miss is not an answer. Leaving it for a person costs a
        # minute; answering the wrong question costs it in public.
        #
        # Logged at info, not debug: a comment that almost matched is the
        # one case where silence looks like a fault, and the closest
        # answer plus its distance is what tells an admin whether to
        # reword the example or leave it alone. Diagnosing this without it
        # meant re-embedding the comment by hand against the library.
        if log_misses:
            log.info(
                "instagram.autoreply.below_threshold closest=%r distance=%.4f "
                "max=%.2f account_id=%s model=%s",
                candidate.trigger,
                float(dist) if dist is not None else -1.0,
                max_distance,
                account_id,
                model,
            )
        return (
            None,
            "below_threshold",
            (float(dist) if dist is not None else None),
            candidate.id,
        )
    return candidate.reply, "semantic_match", float(dist), candidate.id


async def _shadow_match(
    session: AsyncSession,
    *,
    comment: InstagramComment,
    post: InstagramPost,
    rule: InstagramPostAutoreply,
    text: str,
    read_model: str,
    primary: MatchResult,
) -> None:
    """Shadow mode: run the model that is *not* answering and log both.

    Only ever logs. It exists so the switch to the local model is decided
    on real comments: the line says whether the two would have given the
    same answer, and how close each one was."""
    other = MODEL_OPENAI if read_model == MODEL_GEMMA else MODEL_GEMMA
    if not get_settings().embedding_shadow or not _model_enabled(other):
        return
    try:
        shadow = await _semantic_match(
            session,
            account_id=comment.account_id,
            post_id=post.id,
            text=text,
            max_distance=_max_distance_for(rule, other),
            model=other,
            log_misses=False,
        )
    except Exception:
        log.exception(
            "instagram.autoreply.shadow_failed comment=%s", comment.ig_comment_id
        )
        return
    by_model = {read_model: primary, other: shadow}
    oa, gm = by_model[MODEL_OPENAI], by_model[MODEL_GEMMA]
    # Same answer, or both silent.
    same = (oa[0] is None and gm[0] is None) or (
        oa[0] is not None and gm[0] is not None and oa[3] == gm[3]
    )
    log.info(
        "instagram.autoreply.shadow account_id=%s comment=%s reading=%s "
        "openai=(answer=%s %s %s) gemma=(answer=%s %s %s) same_decision=%s",
        comment.account_id,
        comment.ig_comment_id,
        read_model,
        oa[3],
        oa[1],
        _fmt_distance(oa[2]),
        gm[3],
        gm[1],
        _fmt_distance(gm[2]),
        same,
    )


def _fmt_distance(distance: float | None) -> str:
    return "-" if distance is None else f"{distance:.4f}"


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

    # Why a semantic rule declined, kept for the final decision. "no_match"
    # alone cannot tell an admin whether to configure a key, write answers,
    # or loosen the threshold — and that is exactly what they need to know.
    semantic_miss: str | None = None
    # Looked up once, and only when a similarity rule is about to run.
    read_model: str | None = None

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
            if read_model is None:
                read_model = await account_read_model(session, comment.account_id)
            primary = await _semantic_match(
                session,
                account_id=comment.account_id,
                post_id=post.id,
                text=text,
                max_distance=_max_distance_for(rule, read_model),
                model=read_model,
            )
            await _shadow_match(
                session,
                comment=comment,
                post=post,
                rule=rule,
                text=text,
                read_model=read_model,
                primary=primary,
            )
            body, reason, distance, _answer_id = primary
            if body is None:
                # Fall through to a catch-all rule if one exists — a
                # library miss should not block a generic answer.
                semantic_miss = reason
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

    return ReplyDecision(reason=semantic_miss or "no_match")


__all__ = ["ReplyDecision", "decide_reply"]
