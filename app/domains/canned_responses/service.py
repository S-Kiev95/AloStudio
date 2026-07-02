"""CannedResponse CRUD + search-ranking service.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/canned_responses_controller.rb
  reference/chatwoot/app/models/canned_response.rb
    (presence + per-account uniqueness validations, ``order_by_search`` scope)

Search: when ``?search=`` is present the index filters
``short_code ILIKE %q% OR content ILIKE %q%`` and orders by Chatwoot's
``order_by_search`` CASE ranking — a short_code *prefix* hit (1.0)
outranks a short_code *substring* hit (0.5), which outranks a content
substring hit (0.2).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.canned_responses.models import CannedResponse


def _require(value: str | None, label: str) -> str:
    """Rails presence validation → 422 with ``{"message": ...}``."""
    if value is None or not value.strip():
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"{label} can't be blank"},
        )
    return value


async def _ensure_unique_short_code(
    session: AsyncSession,
    *,
    account_id: int,
    short_code: str,
    exclude_id: int | None = None,
) -> None:
    """Mirror ``uniqueness: { scope: :account_id }`` on ``short_code``."""
    stmt = select(CannedResponse).where(
        CannedResponse.account_id == account_id,
        CannedResponse.short_code == short_code,
    )
    if exclude_id is not None:
        stmt = stmt.where(CannedResponse.id != exclude_id)
    if (await session.exec(stmt)).first() is not None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Short code has already been taken"},
        )


async def list_canned_responses(
    session: AsyncSession,
    *,
    account_id: int,
    search: str | None = None,
) -> list[CannedResponse]:
    """Port of ``CannedResponsesController#canned_responses``.

    No search → every response for the account (id order). With search →
    ILIKE on short_code/content plus the ``order_by_search`` ranking.
    """
    stmt = select(CannedResponse).where(
        CannedResponse.account_id == account_id
    )
    if search and search.strip():
        q = search.strip()
        stmt = stmt.where(
            or_(
                CannedResponse.short_code.ilike(f"%{q}%"),  # type: ignore[union-attr]
                CannedResponse.content.ilike(f"%{q}%"),  # type: ignore[union-attr]
            )
        )
        rank = case(
            (CannedResponse.short_code.ilike(f"{q}%"), 1.0),  # type: ignore[union-attr]
            (CannedResponse.short_code.ilike(f"%{q}%"), 0.5),  # type: ignore[union-attr]
            (CannedResponse.content.ilike(f"%{q}%"), 0.2),  # type: ignore[union-attr]
            else_=0.0,
        )
        stmt = stmt.order_by(rank.desc(), CannedResponse.id.asc())  # type: ignore[attr-defined]
    else:
        stmt = stmt.order_by(CannedResponse.id.asc())  # type: ignore[attr-defined]
    return list((await session.exec(stmt)).all())


async def create_canned_response(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> CannedResponse:
    short_code = _require(payload.get("short_code"), "Short code")
    content = _require(payload.get("content"), "Content")
    await _ensure_unique_short_code(
        session, account_id=account_id, short_code=short_code
    )
    cr = CannedResponse(
        account_id=account_id, short_code=short_code, content=content
    )
    session.add(cr)
    await session.flush()
    await session.refresh(cr)
    return cr


async def update_canned_response(
    session: AsyncSession,
    *,
    canned: CannedResponse,
    payload: dict[str, Any],
) -> CannedResponse:
    if "short_code" in payload:
        new_code = _require(payload.get("short_code"), "Short code")
        if new_code != canned.short_code:
            await _ensure_unique_short_code(
                session,
                account_id=canned.account_id,
                short_code=new_code,
                exclude_id=canned.id,
            )
        canned.short_code = new_code
    if "content" in payload:
        canned.content = _require(payload.get("content"), "Content")
    session.add(canned)
    await session.flush()
    await session.refresh(canned)
    return canned


async def destroy_canned_response(
    session: AsyncSession, *, canned: CannedResponse
) -> None:
    await session.delete(canned)
    await session.flush()


__all__ = [
    "create_canned_response",
    "destroy_canned_response",
    "list_canned_responses",
    "update_canned_response",
]
