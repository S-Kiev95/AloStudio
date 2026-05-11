"""Wire-shape presenters for CsatSurveyResponse.

Anchors:
  reference/chatwoot/app/views/api/v1/models/_csat_survey_response.json.jbuilder
"""

from __future__ import annotations

from typing import Any

from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.csat.models import CsatSurveyResponse


def present_response(
    response: CsatSurveyResponse,
    *,
    contact: Contact | None = None,
    conversation: Conversation | None = None,
    assigned_agent: dict[str, Any] | None = None,
    review_notes_updated_by: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mirror ``_csat_survey_response.json.jbuilder`` byte-for-byte.

    The five embedded blocks (review_notes_updated_by, contact,
    assigned_agent) are passed in pre-rendered so the presenter stays
    pure and we don't pull users.presenters into this module."""
    body: dict[str, Any] = {
        "id": response.id,
        "rating": response.rating,
        "feedback_message": response.feedback_message,
        "csat_review_notes": response.csat_review_notes,
        "review_notes_updated_at": (
            int(response.review_notes_updated_at.timestamp())
            if response.review_notes_updated_at
            else None
        ),
    }
    if review_notes_updated_by is not None:
        body["review_notes_updated_by"] = review_notes_updated_by
    body["account_id"] = response.account_id
    body["message_id"] = response.message_id
    if contact is not None:
        # ``_contact.json.jbuilder`` is a 30-field partial; the metrics
        # surface only consumes a thin slice, so we expose id+name+email
        # here and the dashboard fattens it server-side when needed.
        body["contact"] = {
            "id": contact.id,
            "name": contact.name,
            "email": contact.email,
            "phone_number": contact.phone_number,
        }
    body["conversation_id"] = (
        conversation.display_id if conversation is not None else None
    )
    if assigned_agent is not None:
        body["assigned_agent"] = assigned_agent
    body["created_at"] = (
        int(response.created_at.timestamp())
        if response.created_at
        else None
    )
    return body


__all__ = ["present_response"]
