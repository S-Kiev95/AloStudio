"""The help assistant for anyone in the account.

Route map, under ``/api/v1/accounts/{account_id}/help_assistant``:
  * ``GET``  — whether it is on (the panel shows the Ayuda button by it)
  * ``POST`` — ``{question, page?}`` → ``{known, answer, screen, note, seconds}``

Errors carry ``code`` (``help_assistant.<code>``): ``disabled``,
``question``, ``busy`` (the model took too long, usually warming up) and
``failed``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core import local_llm
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.help_assistant import service

router = APIRouter(prefix="/api/v1/accounts/{account_id}/help_assistant", tags=["help_assistant"])


class AskBody(BaseModel):
    question: str
    page: str | None = None


def _fail(code: str, status: int = 422) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=status, detail={"message": code, "code": f"help_assistant.{code}"}
    )


@router.get("")
async def show(ctx: Annotated[AccountContext, Depends(account_context)]) -> dict[str, Any]:
    return {"enabled": service.enabled(), "question_max": service.QUESTION_MAX}


@router.post("")
async def ask(
    body: AskBody, ctx: Annotated[AccountContext, Depends(account_context)]
) -> dict[str, Any]:
    if not service.enabled():
        raise _fail("disabled")
    try:
        return await service.ask(body.question, page=body.page, is_admin=ctx.is_administrator)
    except ValueError as exc:
        raise _fail(str(exc)) from exc
    except local_llm.LocalLlmError as exc:
        code = "busy" if exc.code == "timeout" else "failed"
        raise _fail(code, 503) from exc
