"""Public CSAT survey endpoints — `/public/api/v1/csat_survey/{uuid}`.

Ports ``Public::Api::V1::CsatSurveyController``.

Route map:

  * ``GET /public/api/v1/csat_survey/{uuid}`` — show the ``input_csat``
    message + its current submitted values (used by the public-facing
    survey page rendered to the contact).
  * ``PUT /public/api/v1/csat_survey/{uuid}`` — submit / update the
    rating + feedback.

Auth: this is public — the conversation ``uuid`` IS the credential.
Rails has no separate auth; we mirror that.

Wire shape:
  * ``GET``  → ``{"id": <conv_uuid>, "content_attributes": {...}, ...}``
    (mirrors the message_show jbuilder for ``input_csat``)
  * ``PUT``  → the same shape, with the updated ``submitted_values``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.conversations.models import (
    CONTENT_TYPE_INPUT_CSAT,
    Conversation,
    Message,
)
from app.domains.csat.schemas import CsatUpdateEnvelope
from app.domains.csat.service import submit_csat_response

router = APIRouter(
    prefix="/public/api/v1/csat_survey",
    tags=["public-csat-survey"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _resolve(
    session: AsyncSession, uuid_str: str
) -> tuple[Conversation, Message]:
    from uuid import UUID

    try:
        conv_uuid = UUID(uuid_str)
    except (TypeError, ValueError) as exc:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        ) from exc
    conv = (
        await session.exec(
            select(Conversation).where(Conversation.uuid == conv_uuid)
        )
    ).first()
    if conv is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    msg = (
        await session.exec(
            select(Message).where(
                Message.conversation_id == conv.id,
                Message.content_type == CONTENT_TYPE_INPUT_CSAT,
            )
        )
    ).first()
    if msg is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return conv, msg


def _present_message(msg: Message) -> dict[str, Any]:
    """A thin presenter — the public survey UI consumes a small set
    of fields. Mirrors what Chatwoot's ``message.json.jbuilder`` ships
    for an ``input_csat`` row."""
    return {
        "id": msg.id,
        "content": msg.content,
        "content_type": "input_csat",
        "content_attributes": msg.content_attributes or {},
        "created_at": (
            int(msg.created_at.timestamp()) if msg.created_at else None
        ),
        "conversation_id": msg.conversation_id,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/{uuid}")
async def show_csat(
    uuid: Annotated[str, Path()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    _conv, msg = await _resolve(session, uuid)
    return _present_message(msg)


@router.put("/{uuid}")
async def update_csat(
    uuid: Annotated[str, Path()],
    payload: CsatUpdateEnvelope,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Extract the ``csat_survey_response`` block from
    ``message.submitted_values`` and persist via :func:`submit_csat_response`.

    Mirrors Rails' permit shape: ``submitted_values`` is an array of
    entries, ANY of which may carry the ``csat_survey_response`` block.
    We pull the first one we see — matches Chatwoot's dashboard
    serialisation."""
    conv, _msg = await _resolve(session, uuid)
    response_body = None
    for entry in payload.message.submitted_values:
        if entry.csat_survey_response is not None:
            response_body = entry.csat_survey_response
            break
    if response_body is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "csat_survey_response payload missing"
            },
        )
    updated_msg, _resp = await submit_csat_response(
        session,
        conversation=conv,
        rating=response_body.rating,
        feedback_message=response_body.feedback_message,
    )
    return _present_message(updated_msg)


__all__ = ["router"]
