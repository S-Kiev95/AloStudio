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
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.core.llm import embed_text, embedding_search_enabled
from app.domains.instagram.autoreply_models import (
    InstagramCommentReply,
)
from app.domains.instagram.models import InstagramPost
from app.domains.instagram.post_autoreply_models import (
    DELIVERIES,
    MATCH_KEYWORD,
    MATCH_TYPES,
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


class CommentReplyIn(BaseModel):
    trigger: str = Field(min_length=1)
    reply: str = Field(min_length=1)
    enabled: bool = True


def _present_reply(row: InstagramCommentReply) -> dict[str, Any]:
    return {
        "id": row.id,
        "trigger": row.trigger,
        "reply": row.reply,
        "enabled": row.enabled,
        # Surfaced so the UI can flag an answer that will never match.
        "indexed": row.embedding is not None,
    }


async def _embed_or_none(text: str) -> list[float] | None:
    if not embedding_search_enabled():
        return None
    try:
        return await embed_text(text)
    except Exception:
        log.exception("instagram.autoreply.embed_on_save_failed")
        return None


# ---------------------------------------------------------------------------
# Prepared answers
# ---------------------------------------------------------------------------
@router.get("/instagram_comment_replies")
async def list_replies(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    rows = (
        await session.exec(
            select(InstagramCommentReply)
            .where(InstagramCommentReply.account_id == ctx.account.id)
            .order_by(InstagramCommentReply.id.desc())
        )
    ).all()
    return [_present_reply(r) for r in rows]


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
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _present_reply(row)


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
    # Re-embed only when the matched text actually changed — editing the
    # answer's wording must not cost an OpenAI call.
    if trigger != row.trigger:
        row.embedding = await _embed_or_none(trigger)
    row.trigger = trigger
    row.reply = payload.reply.strip()
    row.enabled = payload.enabled
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _present_reply(row)


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
    }


async def _owned_post(
    session: AsyncSession, *, post_id: int, account_id: int
) -> InstagramPost:
    post = await session.get(InstagramPost, post_id)
    if post is None or post.account_id != account_id:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return post


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
            .order_by(InstagramPostAutoreply.id.asc())
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
