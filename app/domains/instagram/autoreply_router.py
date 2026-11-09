"""Admin API for Instagram comment auto-reply.

Two surfaces: the rules attached to one publication, and the account-wide
library of prepared answers that ``semantic`` rules match against. The
library is account-level on purpose — the same answers about shipping or
prices apply across every post.

Answers are embedded when written, not when matched — matching happens
inside a webhook, where a per-comment OpenAI round-trip would be both slow
and repeated. A save that cannot embed still stores the answer with a null
vector, which simply means it is not offered until re-saved; that is a
better failure than losing the text the admin just typed.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import case, delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.embeddings import (
    MODEL_GEMMA,
    TASK_CLASSIFICATION,
    embed_gemma_one,
    gemma_enabled,
    read_model_from,
)
from app.core.errors import ChatwootHTTPException
from app.core.llm import embed_text, embedding_search_enabled
from app.domains.instagram.autoreply_models import (
    DEFAULT_MATCH_MAX_DISTANCE,
    DEFAULT_MATCH_MAX_DISTANCE_GEMMA,
    InstagramCommentReply,
    InstagramPostReplyPick,
)
from app.domains.instagram.models import InstagramPost
from app.domains.instagram.post_autoreply_models import (
    DELIVERIES,
    MATCH_KEYWORD,
    MATCH_PRIORITY,
    MATCH_TYPES,
    MAX_MATCH_DISTANCE,
    MAX_MATCH_DISTANCE_GEMMA,
    MIN_MATCH_DISTANCE,
    MIN_MATCH_DISTANCE_GEMMA,
    InstagramPostAutoreply,
)

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}",
    tags=["instagram-autoreply"],
)


class PostRuleIn(BaseModel):
    match_type: str = MATCH_KEYWORD
    keywords: str | None = None
    reply_text: str | None = None
    delivery: str = "public"
    enabled: bool = True
    # Null follows the installation default. Only meaningful for
    # ``semantic``; the other modes do not match by distance.
    max_distance: float | None = None
    # The same for the local model, on its own scale. On an edit, a field
    # left out of the payload keeps its stored value: a form showing one
    # model's setting must not wipe the other's.
    max_distance_gemma: float | None = None


class CommentReplyIn(BaseModel):
    trigger: str = Field(min_length=1)
    reply: str = Field(min_length=1)
    enabled: bool = True


class ReplyPicksIn(BaseModel):
    """The answers a publication offers. Empty means "the whole library"."""

    reply_ids: list[int] = Field(default_factory=list)


def _present_reply(
    row: InstagramCommentReply,
    *,
    model: str,
    picked: set[int] | None = None,
) -> dict[str, Any]:
    vector = row.embedding_gemma if model == MODEL_GEMMA else row.embedding
    out: dict[str, Any] = {
        "id": row.id,
        "trigger": row.trigger,
        "reply": row.reply,
        "enabled": row.enabled,
        # Surfaced so the UI can flag an answer that will never match —
        # with the model this account reads with.
        "indexed": vector is not None,
    }
    if picked is not None:
        out["selected"] = row.id in picked
    return out


async def _embed_or_none(text: str) -> list[float] | None:
    if not embedding_search_enabled():
        return None
    try:
        return await embed_text(text)
    except Exception:
        log.exception("instagram.autoreply.embed_on_save_failed")
        return None


async def _embed_gemma_or_none(text: str) -> list[float] | None:
    """The trigger embedded by the local model, or None.

    Written on every save while the service is configured, whichever model
    the account reads with: that is what lets an account switch (and switch
    back) without re-saving its library."""
    if not gemma_enabled():
        return None
    try:
        return await embed_gemma_one(text, task=TASK_CLASSIFICATION) or None
    except Exception:
        log.exception("instagram.autoreply.embed_gemma_on_save_failed")
        return None


def _read_model(ctx: AccountContext) -> str:
    return read_model_from(ctx.account.internal_attributes)


def _semantic_available(model: str) -> bool:
    if model == MODEL_GEMMA:
        return gemma_enabled()
    return embedding_search_enabled()


async def _owned_post(
    session: AsyncSession, *, post_id: int, account_id: int
) -> InstagramPost:
    post = await session.get(InstagramPost, post_id)
    if post is None or post.account_id != account_id:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return post


async def _picked_ids(session: AsyncSession, *, post_id: int) -> set[int]:
    return set(
        (
            await session.exec(
                select(InstagramPostReplyPick.comment_reply_id).where(
                    InstagramPostReplyPick.post_id == post_id
                )
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# Prepared answers
# ---------------------------------------------------------------------------
@router.get("/instagram_autoreply_status")
async def autoreply_status(
    ctx: Annotated[AccountContext, Depends(require_admin)],
) -> dict[str, Any]:
    """Whether similarity matching can run on this installation at all.

    Without an embedding provider a ``semantic`` rule is silently inert and
    every answer saves unindexed. The UI needs to say that plainly instead
    of telling the admin to save again, which cannot help.
    """
    model = _read_model(ctx)
    # ``embedding_model`` tells the form which strictness scale to show.
    return {
        "semantic_available": _semantic_available(model),
        "embedding_model": model,
    }


@router.get("/instagram_comment_replies")
async def list_replies(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    post_id: int | None = None,
) -> list[dict[str, Any]]:
    """The account's answers.

    With ``post_id`` every row also carries ``selected`` — whether that
    publication offers it. The list is the whole library either way: the
    picker has to show what is *not* picked as much as what is.
    """
    rows = (
        await session.exec(
            select(InstagramCommentReply)
            .where(InstagramCommentReply.account_id == ctx.account.id)
            .order_by(InstagramCommentReply.id.desc())
        )
    ).all()
    model = _read_model(ctx)
    if post_id is None:
        return [_present_reply(r, model=model) for r in rows]
    await _owned_post(session, post_id=post_id, account_id=ctx.account.id)
    picked = await _picked_ids(session, post_id=post_id)
    return [_present_reply(r, model=model, picked=picked) for r in rows]


@router.post("/instagram_comment_replies", status_code=status.HTTP_200_OK)
async def create_reply_entry(
    payload: CommentReplyIn,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    row = InstagramCommentReply(
        account_id=ctx.account.id,
        trigger=payload.trigger.strip(),
        reply=payload.reply.strip(),
        enabled=payload.enabled,
        embedding=await _embed_or_none(payload.trigger),
        embedding_gemma=await _embed_gemma_or_none(payload.trigger),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _present_reply(row, model=_read_model(ctx))


@router.patch("/instagram_comment_replies/{reply_id}")
async def update_reply_entry(
    reply_id: Annotated[int, Path()],
    payload: CommentReplyIn,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await session.get(InstagramCommentReply, reply_id)
    if row is None or row.account_id != ctx.account.id:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    trigger = payload.trigger.strip()
    # Re-embed when the matched text changed, or when a previous save could
    # not embed at all — re-saving is the documented way to fix that, so it
    # has to actually retry.
    if trigger != row.trigger or row.embedding is None:
        row.embedding = await _embed_or_none(trigger)
    if trigger != row.trigger or row.embedding_gemma is None:
        row.embedding_gemma = await _embed_gemma_or_none(trigger)
    row.trigger = trigger
    row.reply = payload.reply.strip()
    row.enabled = payload.enabled
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _present_reply(row, model=_read_model(ctx))


@router.delete(
    "/instagram_comment_replies/{reply_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_reply_entry(
    reply_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await session.get(InstagramCommentReply, reply_id)
    if row is None or row.account_id != ctx.account.id:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    await session.delete(row)
    await session.commit()
    return {}


@router.put("/instagram_posts/{post_id}/comment_replies")
async def set_reply_picks(
    post_id: Annotated[int, Path()],
    payload: ReplyPicksIn,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Replace which answers this publication offers.

    Whole-set replace rather than add/remove calls: the UI edits a list of
    checkboxes, and sending the resulting set makes a lost request leave
    the selection as it was instead of half-applied.

    An empty list clears the picks, which means the post falls back to the
    whole library — the same as never having picked.
    """
    await _owned_post(session, post_id=post_id, account_id=ctx.account.id)

    # Only ids the account owns; a foreign id is dropped rather than
    # trusted into a row that would leak another account's answer.
    wanted = set(
        (
            await session.exec(
                select(InstagramCommentReply.id).where(
                    InstagramCommentReply.account_id == ctx.account.id,
                    InstagramCommentReply.id.in_(payload.reply_ids or [-1]),
                )
            )
        ).all()
    )
    current = await _picked_ids(session, post_id=post_id)

    for reply_id in wanted - current:
        session.add(
            InstagramPostReplyPick(post_id=post_id, comment_reply_id=reply_id)
        )
    if current - wanted:
        await session.exec(
            delete(InstagramPostReplyPick).where(
                InstagramPostReplyPick.post_id == post_id,
                InstagramPostReplyPick.comment_reply_id.in_(current - wanted),
            )
        )
    await session.commit()
    return {"post_id": post_id, "reply_ids": sorted(wanted)}


# ---------------------------------------------------------------------------
# Rules on one publication
# ---------------------------------------------------------------------------
def _present_rule(row: InstagramPostAutoreply) -> dict[str, Any]:
    return {
        "id": row.id,
        "post_id": row.post_id,
        "match_type": row.match_type,
        "keywords": row.keywords,
        "reply_text": row.reply_text,
        "delivery": row.delivery,
        "enabled": row.enabled,
        "max_distance": row.max_distance,
        # What the rule is actually matching at, so the UI never has to
        # hardcode the default to show it.
        "effective_max_distance": row.max_distance or DEFAULT_MATCH_MAX_DISTANCE,
        "max_distance_gemma": row.max_distance_gemma,
        "effective_max_distance_gemma": (
            row.max_distance_gemma or DEFAULT_MATCH_MAX_DISTANCE_GEMMA
        ),
    }


def _apply_distances(row: InstagramPostAutoreply, payload: PostRuleIn) -> None:
    """Write each model's threshold — on an edit, only the ones sent.

    Only a ``semantic`` rule matches by distance; storing one on a keyword
    or catch-all rule would show a setting that changes nothing, so
    switching away from ``semantic`` clears both. The form shows the scale
    of the model the account reads with and sends only that field: the
    other model's value (an OpenAI threshold tuned before the switch, say)
    must survive the edit untouched."""
    if payload.match_type != "semantic":
        row.max_distance = None
        row.max_distance_gemma = None
        return
    sent = payload.model_fields_set
    if row.id is None or "max_distance" in sent:
        row.max_distance = payload.max_distance
    if row.id is None or "max_distance_gemma" in sent:
        row.max_distance_gemma = payload.max_distance_gemma


def _match_order():
    """Sort key mirroring ``MATCH_PRIORITY`` — the evaluation order."""
    return case(
        MATCH_PRIORITY,
        value=InstagramPostAutoreply.match_type,
        else_=99,
    )


def _validate_rule(payload: PostRuleIn) -> None:
    if payload.match_type not in MATCH_TYPES:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"match_type debe ser uno de {', '.join(MATCH_TYPES)}"},
        )
    if payload.delivery not in DELIVERIES:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"delivery debe ser uno de {', '.join(DELIVERIES)}"},
        )
    # Refusing here beats storing a rule that can never fire and leaving
    # the admin to wonder why nothing happens.
    if payload.match_type == "keyword" and not (payload.keywords or "").strip():
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Una regla por palabra clave necesita al menos una palabra"},
        )
    if payload.match_type in ("keyword", "all") and not (
        payload.reply_text or ""
    ).strip():
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Falta el texto de la respuesta"},
        )
    # Bounded: past the top of the range every comment matches its nearest
    # answer, which is the failure mode the threshold exists to prevent.
    if payload.max_distance is not None and not (
        MIN_MATCH_DISTANCE <= payload.max_distance <= MAX_MATCH_DISTANCE
    ):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"La exigencia debe estar entre {MIN_MATCH_DISTANCE} "
                    f"y {MAX_MATCH_DISTANCE}"
                )
            },
        )
    if payload.max_distance_gemma is not None and not (
        MIN_MATCH_DISTANCE_GEMMA <= payload.max_distance_gemma <= MAX_MATCH_DISTANCE_GEMMA
    ):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"La exigencia debe estar entre {MIN_MATCH_DISTANCE_GEMMA} "
                    f"y {MAX_MATCH_DISTANCE_GEMMA}"
                )
            },
        )


@router.get("/instagram_posts/{post_id}/autoreply_rules")
async def list_rules(
    post_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    await _owned_post(session, post_id=post_id, account_id=ctx.account.id)
    rows = (
        await session.exec(
            select(InstagramPostAutoreply)
            .where(InstagramPostAutoreply.post_id == post_id)
            # Listed in the order they are evaluated, not the order they
            # were written. A catch-all shown above a keyword rule reads as
            # if it swallowed everything — the opposite of what happens.
            .order_by(
                _match_order(), InstagramPostAutoreply.id.asc()
            )
        )
    ).all()
    return [_present_rule(r) for r in rows]


@router.post(
    "/instagram_posts/{post_id}/autoreply_rules",
    status_code=status.HTTP_200_OK,
)
async def create_rule(
    post_id: Annotated[int, Path()],
    payload: PostRuleIn,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    await _owned_post(session, post_id=post_id, account_id=ctx.account.id)
    _validate_rule(payload)
    row = InstagramPostAutoreply(
        account_id=ctx.account.id,
        post_id=post_id,
        match_type=payload.match_type,
        keywords=(payload.keywords or "").strip() or None,
        reply_text=(payload.reply_text or "").strip() or None,
        delivery=payload.delivery,
        enabled=payload.enabled,
    )
    _apply_distances(row, payload)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _present_rule(row)


@router.patch("/autoreply_rules/{rule_id}")
async def update_rule(
    rule_id: Annotated[int, Path()],
    payload: PostRuleIn,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await session.get(InstagramPostAutoreply, rule_id)
    if row is None or row.account_id != ctx.account.id:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    _validate_rule(payload)
    row.match_type = payload.match_type
    row.keywords = (payload.keywords or "").strip() or None
    row.reply_text = (payload.reply_text or "").strip() or None
    row.delivery = payload.delivery
    row.enabled = payload.enabled
    _apply_distances(row, payload)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _present_rule(row)


@router.delete("/autoreply_rules/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_rule(
    rule_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await session.get(InstagramPostAutoreply, rule_id)
    if row is None or row.account_id != ctx.account.id:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    await session.delete(row)
    await session.commit()
    return {}


__all__ = ["router"]
