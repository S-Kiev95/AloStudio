"""The help assistant for anyone in the account.

Route map, under ``/api/v1/accounts/{account_id}/help_assistant``:
  * ``GET``           — the modes this account can use (``free``: the local
    model; ``fast``: OpenAI, when an administrator allowed it), and whether
    the user can change that
  * ``PUT /settings`` — ``{fast}``: an administrator allows or stops Fast
  * ``POST``          — ``{question, page?, mode?}`` →
    ``{known, answer, screen, note, seconds, mode}``

Errors carry ``code`` (``help_assistant.<code>``): ``disabled``, ``mode``,
``question``, ``budget`` (the account's AI cap), ``busy`` (the local model
took too long, usually warming up) and ``failed``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import llm, local_llm
from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.help_assistant import service

router = APIRouter(prefix="/api/v1/accounts/{account_id}/help_assistant", tags=["help_assistant"])


class AskBody(BaseModel):
    question: str
    page: str | None = None
    mode: str | None = None


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
    try:
        return await service.ask(
            body.question,
            page=body.page,
            is_admin=ctx.is_administrator,
            mode=mode,
            session=session,
            account_id=ctx.account.id,
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc
    except local_llm.LocalLlmError as exc:
        code = {"timeout": "busy", "rate_limited": "limit"}.get(exc.code, "failed")
        raise _fail(code, 503) from exc
    except llm.LlmError as exc:
        raise _fail("failed", 503) from exc
