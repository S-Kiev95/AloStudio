"""The help assistant for anyone in the account.

Route map, under ``/api/v1/accounts/{account_id}/help_assistant``:
  * ``GET``           — the modes this account can use (``free``: the local
    model; ``fast``: OpenAI, when an administrator allowed it), and whether
    the user can change that
  * ``PUT /settings`` — ``{fast}``: an administrator allows or stops Fast
  * ``POST``          — ``{question, page?, mode?}`` →
    ``{known, answer, screen, note, seconds, mode}``

``image`` and ``audio`` (data URLs) are turned into text first by
:mod:`app.core.media_ai` (NVIDIA, then Groq); the answer says what was heard
and seen.

Errors carry ``code`` (``help_assistant.<code>``): ``disabled``, ``mode``,
``question``, ``budget`` (the account's AI cap), ``busy`` (the local model
took too long, usually warming up), ``ai_down`` (no free provider could
answer), ``media_off``, ``media_type``, ``media_size`` and ``failed``.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import llm, local_llm, media_ai
from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.help_assistant import service

router = APIRouter(prefix="/api/v1/accounts/{account_id}/help_assistant", tags=["help_assistant"])


class AskBody(BaseModel):
    question: str = ""
    page: str | None = None
    mode: str | None = None
    # ``data:<type>;base64,…``: a screenshot and/or a voice question.
    image: str | None = None
    audio: str | None = None


def _data_url(value: str) -> tuple[str, bytes]:
    match = re.fullmatch(r"data:([\w/+.-]+(?:;[\w=.-]+)*);base64,(.+)", value.strip(), re.S)
    if match is None:
        raise media_ai.MediaRejected("type")
    mime = match.group(1).split(";")[0]
    try:
        return mime, base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise media_ai.MediaRejected("type") from exc


class SettingsBody(BaseModel):
    fast: bool


def _fail(code: str, status: int = 422) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=status, detail={"message": code, "code": f"help_assistant.{code}"}
    )


def _present(ctx: AccountContext) -> dict[str, Any]:
    modes = service.modes(ctx.account)
    return {
        "enabled": bool(modes),
        "modes": modes,
        "fast_possible": service.fast_possible(),
        "fast_allowed": service.fast_allowed(ctx.account),
        "can_manage": ctx.is_administrator,
        "question_max": service.QUESTION_MAX,
        # Screenshots and voice questions (NVIDIA or Groq keys set).
        "media": media_ai.available(),
    }


@router.get("")
async def show(ctx: Annotated[AccountContext, Depends(account_context)]) -> dict[str, Any]:
    return _present(ctx)


@router.put("/settings")
async def update_settings(
    body: SettingsBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    service.allow_fast(ctx.account, body.fast)
    session.add(ctx.account)
    await session.flush()
    return _present(ctx)


@router.post("")
async def ask(
    body: AskBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    modes = service.modes(ctx.account)
    if not modes:
        raise _fail("disabled")
    mode = body.mode or modes[0]
    if mode not in modes:
        raise _fail("mode")
    question, heard, seen = body.question, None, None
    if body.image or body.audio:
        if not media_ai.available():
            raise _fail("media_off")
        try:
            if body.audio:
                mime, data = _data_url(body.audio)
                media_ai.check("audio", mime, data)
                heard = await media_ai.transcribe(data, mime)
                question = f"{heard} {question}".strip()
            if body.image:
                mime, data = _data_url(body.image)
                media_ai.check("image", mime, data)
                seen = await media_ai.describe(data, mime)
                question = f"{question}\n(Captura de la pantalla de la persona: {seen})".strip()
        except media_ai.MediaRejected as exc:
            raise _fail(f"media_{exc.code}") from exc
        except media_ai.MediaAiDown as exc:
            raise _fail("ai_down", 503) from exc
    try:
        answer = await service.ask(
            question,
            page=body.page,
            is_admin=ctx.is_administrator,
            mode=mode,
            session=session,
            account_id=ctx.account.id,
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc
    except local_llm.LocalLlmError as exc:
        if local_llm.hosted():
            # Every free provider was asked and none could answer.
            raise _fail("ai_down", 503) from exc
        code = {"timeout": "busy", "rate_limited": "limit"}.get(exc.code, "failed")
        raise _fail(code, 503) from exc
    except llm.LlmError as exc:
        raise _fail("failed", 503) from exc
    return {**answer, "heard": heard, "seen": seen}
