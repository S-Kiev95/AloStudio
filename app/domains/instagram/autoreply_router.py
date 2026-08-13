"""Admin API for Instagram comment auto-reply.

Two surfaces: the per-inbox switch, and the library of prepared answers
that the semantic mode matches against.

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
from app.domains.instagram import connect_service
from app.domains.instagram.autoreply_models import (
    AUTOREPLY_MODES,
    DEFAULT_MATCH_MAX_DISTANCE,
    InstagramCommentReply,
)

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}",
    tags=["instagram-autoreply"],
)


class AutoreplyConfigIn(BaseModel):
    mode: str | None = None
    text: str | None = None
    max_distance: float | None = Field(default=None, ge=0.0, le=2.0)


class CommentReplyIn(BaseModel):
    trigger: str = Field(min_length=1)
    reply: str = Field(min_length=1)
    enabled: bool = True


def _present_config(setting: Any) -> dict[str, Any]:
    return {
        "channel_instagram_id": setting.channel_instagram_id,
        "mode": setting.comment_autoreply_mode or "off",
        "text": setting.comment_autoreply_text,
        "max_distance": setting.comment_autoreply_max_distance
        or DEFAULT_MATCH_MAX_DISTANCE,
        # Lets the UI explain why the semantic option is unavailable rather
        # than letting an admin pick a mode that silently never fires.
        "semantic_available": embedding_search_enabled(),
    }


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
# Per-inbox configuration
# ---------------------------------------------------------------------------
@router.get("/instagram_channels/{channel_id}/autoreply")
async def show_config(
    channel_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    setting = await connect_service.get_channel_setting(
        session, channel_instagram_id=channel_id
    )
    if setting is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return _present_config(setting)


@router.patch("/instagram_channels/{channel_id}/autoreply")
async def update_config(
    channel_id: Annotated[int, Path()],
    payload: AutoreplyConfigIn,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    setting = await connect_service.get_channel_setting(
        session, channel_instagram_id=channel_id
    )
    if setting is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )

    if payload.mode is not None:
        if payload.mode not in AUTOREPLY_MODES:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": f"mode must be one of {', '.join(AUTOREPLY_MODES)}"
                },
            )
        # Refusing here beats accepting a mode that would never fire and
        # leaving the admin to wonder why nothing happens.
        if payload.mode == "fixed" and not (
            payload.text or setting.comment_autoreply_text or ""
        ).strip():
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "El modo fijo necesita un texto de respuesta"},
            )
        setting.comment_autoreply_mode = payload.mode
    if payload.text is not None:
        setting.comment_autoreply_text = payload.text
    if payload.max_distance is not None:
        setting.comment_autoreply_max_distance = payload.max_distance

    session.add(setting)
    await session.commit()
    await session.refresh(setting)
    return _present_config(setting)


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


__all__ = ["router"]
