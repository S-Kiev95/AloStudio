"""CSAT survey service — send + submit + metrics.

Ported from:
  reference/chatwoot/app/services/message_templates/template/csat_survey.rb
    (the post-resolve survey template that emits an ``input_csat`` message)
  reference/chatwoot/app/controllers/public/api/v1/csat_survey_controller.rb
    (contact submission endpoint, 14-day lock check)
  reference/chatwoot/app/controllers/api/v1/accounts/csat_survey_responses_controller.rb
    (dashboard listing + metrics)

Three entry points:

  * :func:`send_csat_message_on_resolve` — called from the
    conversation-resolved hook. Idempotent: only one ``input_csat``
    message per conversation.
  * :func:`submit_csat_response` — used by the public update endpoint.
    Upserts the ``CsatSurveyResponse`` row keyed on
    ``message_id`` and rejects updates beyond 14 days.
  * :func:`metrics_for_account` — counts + by-rating breakdown for the
    dashboard widget.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func as sa_func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.conversations.models import (
    CONTENT_TYPE_INPUT_CSAT,
    MESSAGE_TYPE_TEMPLATE,
    Conversation,
    Message,
)
from app.domains.csat.models import (
    CSAT_LOCK_DAYS,
    CSAT_VALID_RATINGS,
    CsatSurveyResponse,
)
from app.domains.inboxes.models import Inbox

log = logging.getLogger(__name__)

# Default message body — mirrors Chatwoot's
# ``conversations.templates.csat_input_message_body`` i18n key (English).
DEFAULT_CSAT_INPUT_MESSAGE = "Please rate the conversation"


# ---------------------------------------------------------------------------
# Send-on-resolve
# ---------------------------------------------------------------------------
async def send_csat_message_on_resolve(
    session: AsyncSession,
    *,
    conversation: Conversation,
) -> Message | None:
    """Insert an ``input_csat`` template message on the conversation.

    Returns the new Message, or ``None`` when the survey was skipped:
      * inbox row missing
      * inbox.csat_survey_enabled is false
      * an ``input_csat`` message already exists on the conversation

    This is the parity of ``MessageTemplates::Template::CsatSurvey``.
    The Rails template enqueues itself via ``HookListener`` on
    ``conversation.resolved`` — we hook from the same dispatcher event
    instead (see :func:`app.domains.csat.listener.fan_out_to_csat`).
    """
    if conversation.id is None:
        return None
    inbox = conversation.inbox
    if inbox is None:
        inbox = await session.get(Inbox, conversation.inbox_id)
    if inbox is None or not inbox.csat_survey_enabled:
        return None

    # Idempotency — Rails relies on ``HookListener``'s ``performed?``
    # audit; we look up the message directly.
    existing = (
        await session.exec(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.content_type == CONTENT_TYPE_INPUT_CSAT,
            )
        )
    ).first()
    if existing is not None:
        return None

    csat_config = inbox.csat_config or {}
    message_content = (
        csat_config.get("message")
        if isinstance(csat_config, dict)
        and isinstance(csat_config.get("message"), str)
        and csat_config["message"].strip()
        else DEFAULT_CSAT_INPUT_MESSAGE
    )
    display_type = (
        csat_config.get("display_type")
        if isinstance(csat_config, dict)
        else None
    )
    if not isinstance(display_type, str) or not display_type:
        display_type = "emoji"

    msg = Message(
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        message_type=MESSAGE_TYPE_TEMPLATE,
        content_type=CONTENT_TYPE_INPUT_CSAT,
        content=message_content,
        content_attributes={"display_type": display_type},
        private=False,
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# Public submit
# ---------------------------------------------------------------------------
def _is_csat_locked(message: Message, *, now: datetime | None = None) -> bool:
    """Mirror ``check_csat_locked`` — the public endpoint refuses
    updates after 14 days from the ``input_csat`` message creation."""
    if message.created_at is None:
        return False
    ref = now or datetime.now(UTC)
    return (ref.date() - message.created_at.date()).days > CSAT_LOCK_DAYS


async def submit_csat_response(
    session: AsyncSession,
    *,
    conversation: Conversation,
    rating: int,
    feedback_message: str | None = None,
) -> tuple[Message, CsatSurveyResponse]:
    """Upsert a CSAT response onto the conversation's ``input_csat``
    message.

    Mirrors Chatwoot's update flow:
      * Reject ratings outside 1..5.
      * Reject when the message is older than 14 days
        (Chatwoot's ``check_csat_locked``).
      * Set ``message.submitted_values`` with the response so the
        dashboard's input_csat widget renders the rating.
      * Upsert a :class:`CsatSurveyResponse` row keyed on ``message_id``.
        Subsequent calls within the 14-day window REPLACE the rating
        + feedback (matches Rails' ``update!`` semantics).
    """
    if rating not in CSAT_VALID_RATINGS:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Rating must be one of 1..5"},
        )

    message = (
        await session.exec(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.content_type == CONTENT_TYPE_INPUT_CSAT,
            )
        )
    ).first()
    if message is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    if _is_csat_locked(message):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "error": "You cannot update the CSAT survey after 14 days"
            },
        )

    # Stamp the response onto the message's submitted_values — matches
    # the public controller's
    # ``params.permit(message: [{ submitted_values: [...] }])`` write.
    ca = dict(message.content_attributes or {})
    submitted = {
        "csat_survey_response": {
            "rating": rating,
            "feedback_message": feedback_message,
        }
    }
    ca["submitted_values"] = submitted
    message.content_attributes = ca
    session.add(message)
    await session.flush()

    # Upsert the response row keyed on message_id (UNIQUE).
    existing = (
        await session.exec(
            select(CsatSurveyResponse).where(
                CsatSurveyResponse.message_id == message.id
            )
        )
    ).first()
    if existing is None:
        if conversation.contact_id is None:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "Conversation has no contact"},
            )
        existing = CsatSurveyResponse(
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            message_id=message.id,
            contact_id=conversation.contact_id,
            rating=rating,
            feedback_message=feedback_message,
            assigned_agent_id=conversation.assignee_id,
        )
        session.add(existing)
        await session.flush()
    else:
        existing.rating = rating
        existing.feedback_message = feedback_message
        existing.assigned_agent_id = conversation.assignee_id
        session.add(existing)
        await session.flush()

    await session.refresh(existing)
    await session.refresh(message)
    return message, existing


# ---------------------------------------------------------------------------
# Dashboard list + metrics
# ---------------------------------------------------------------------------
async def list_responses_for_account(
    session: AsyncSession,
    *,
    account_id: int,
    rating: int | None = None,
    user_ids: list[int] | None = None,
    inbox_id: int | None = None,
    team_id: int | None = None,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    page: int = 1,
    per_page: int = 25,
) -> list[CsatSurveyResponse]:
    """Mirror ``set_csat_survey_responses`` + ``filter_*`` scopes."""
    stmt = select(CsatSurveyResponse).where(
        CsatSurveyResponse.account_id == account_id
    )
    if rating is not None:
        stmt = stmt.where(CsatSurveyResponse.rating == rating)
    if user_ids:
        stmt = stmt.where(
            CsatSurveyResponse.assigned_agent_id.in_(user_ids)  # type: ignore[union-attr]
        )
    if inbox_id is not None or team_id is not None:
        stmt = stmt.join(
            Conversation,
            Conversation.id == CsatSurveyResponse.conversation_id,
        )
        if inbox_id is not None:
            stmt = stmt.where(Conversation.inbox_id == inbox_id)
        if team_id is not None:
            stmt = stmt.where(Conversation.team_id == team_id)
    if range_start is not None:
        stmt = stmt.where(CsatSurveyResponse.created_at >= range_start)
    if range_end is not None:
        stmt = stmt.where(CsatSurveyResponse.created_at <= range_end)
    stmt = stmt.order_by(CsatSurveyResponse.created_at.desc())  # type: ignore[attr-defined]
    offset = max(page - 1, 0) * per_page
    stmt = stmt.offset(offset).limit(per_page)
    return list((await session.exec(stmt)).all())


async def metrics_for_account(
    session: AsyncSession,
    *,
    account_id: int,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> dict[str, Any]:
    """Mirror ``CsatSurveyResponsesController#metrics``.

    Returns:
      * total_count: number of CsatSurveyResponse rows in range
      * ratings_count: ``{rating_int: count_int}``
      * total_sent_messages_count: number of ``input_csat`` messages
        sent in range (denominator for response-rate dashboards)
    """
    base_resp = select(CsatSurveyResponse).where(
        CsatSurveyResponse.account_id == account_id
    )
    if range_start is not None:
        base_resp = base_resp.where(
            CsatSurveyResponse.created_at >= range_start
        )
    if range_end is not None:
        base_resp = base_resp.where(
            CsatSurveyResponse.created_at <= range_end
        )
    responses = list((await session.exec(base_resp)).all())
    total_count = len(responses)
    ratings_count: dict[int, int] = {}
    for r in responses:
        ratings_count[r.rating] = ratings_count.get(r.rating, 0) + 1

    sent_stmt = (
        select(sa_func.count())
        .select_from(Message)
        .where(Message.account_id == account_id)
        .where(Message.content_type == CONTENT_TYPE_INPUT_CSAT)
    )
    if range_start is not None:
        sent_stmt = sent_stmt.where(Message.created_at >= range_start)
    if range_end is not None:
        sent_stmt = sent_stmt.where(Message.created_at <= range_end)
    total_sent = int((await session.exec(sent_stmt)).one() or 0)  # type: ignore[call-overload]

    return {
        "total_count": total_count,
        "ratings_count": ratings_count,
        "total_sent_messages_count": total_sent,
    }


__all__ = [
    "DEFAULT_CSAT_INPUT_MESSAGE",
    "list_responses_for_account",
    "metrics_for_account",
    "send_csat_message_on_resolve",
    "submit_csat_response",
]


# Late-import sanity — sqlmodel mapper config can need a poke for the
# Conversation/Inbox classes when this module is first loaded.
_ = (Conversation, Inbox)
