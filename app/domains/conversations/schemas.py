"""Request bodies for the conversations + messages endpoints.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/conversations_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/conversations/messages_controller.rb
  reference/chatwoot/app/builders/conversation_builder.rb
  reference/chatwoot/app/builders/messages/message_builder.rb

Rails-ism parity notes:

* Chatwoot's controllers call ``params.permit(...)`` which silently drops
  unknown keys. We mirror that with ``extra='ignore'`` on each model so
  surplus fields don't 422.
* Most endpoints take a flat body (no ``conversation:`` wrapper).
* ``snoozed_until`` comes in as an ISO-8601 string; we accept str and
  parse in the router to keep the wire shape Rails-compatible (``DateTime.parse``).
* ``attachments`` in the message body are declared as a list of arbitrary
  dicts on the wire — Chatwoot accepts both multipart file uploads and
  inline URL metadata. Phase 4a accepts only the URL-metadata shape.
* ``custom_attributes`` on the PUT ``/custom_attributes`` endpoint is
  nested: Rails does ``params.permit(custom_attributes: {})[:custom_attributes]``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


# =========================================================================
# POST /api/v1/accounts/:account_id/conversations
# =========================================================================
class MessageInConversationCreate(BaseModel):
    """Inline ``message`` block on ``POST /conversations``.

    The Rails builder accepts these kwargs + passes them through
    ``Messages::MessageBuilder``. We accept the same shape plus
    ``echo_id`` (attr_accessor surface-through), ``attachments``
    (list of {file_type, external_url, ...}), and optional
    ``content_attributes``.
    """

    model_config = ConfigDict(extra="ignore")

    content: str | None = None
    message_type: str = "outgoing"
    content_type: str | None = None
    content_attributes: dict[str, Any] | None = None
    additional_attributes: dict[str, Any] | None = None
    private: bool = False
    source_id: str | None = None
    echo_id: str | None = None
    # Phase 4a: URL-metadata attachments only (no multipart upload).
    attachments: list[dict[str, Any]] | None = None
    # Email-only ride-along (stored verbatim, SMTP pipeline in Phase 5b).
    cc_emails: str | None = None
    bcc_emails: str | None = None
    to_emails: str | None = None


class ConversationCreateRequest(BaseModel):
    """Flat body for ``POST /conversations``.

    ``inbox_id`` + ``contact_id`` + ``source_id`` live outside the
    ``permit`` list but the controller reads them for
    ``build_contact_inbox`` — same pattern as the contacts router.

    ``status`` accepts the string enum (``open``/``resolved``/``pending``/
    ``snoozed``). ``snoozed_until`` comes in as ISO-8601; parsing happens
    in the router so we can give a clean 422 on malformed input.
    """

    model_config = ConfigDict(extra="ignore")

    # Outer lookup keys (Rails' ``contact`` / ``inbox`` / ``contact_inbox``
    # before_actions read these before the permit step).
    inbox_id: int | None = None
    contact_id: int | None = None
    source_id: str | None = None

    # Permitted conversation params.
    additional_attributes: dict[str, Any] | None = None
    custom_attributes: dict[str, Any] | None = None
    status: str | None = None
    snoozed_until: str | None = None  # ISO-8601
    assignee_id: int | None = None
    team_id: int | None = None

    # Inline message block (optional).
    message: MessageInConversationCreate | None = None


# =========================================================================
# PATCH /conversations/:id   (``update`` action)
# =========================================================================
class ConversationUpdateRequest(BaseModel):
    """Only ``priority`` is in Rails' ``permitted_update_params`` today.

    See the ``TODO: Move the other conversation attributes...`` in the
    Ruby controller — Chatwoot themselves haven't consolidated the
    per-field endpoints yet. We mirror the current contract exactly.
    """

    model_config = ConfigDict(extra="ignore")

    priority: str | None = None


# =========================================================================
# POST /conversations/:id/toggle_status
# =========================================================================
class ConversationToggleStatusRequest(BaseModel):
    """``status`` is optional — missing triggers the ``toggle_status``
    flip semantics (open↔resolved, pending/snoozed→open).

    ``snoozed_until`` is only meaningful when ``status='snoozed'``.
    """

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    snoozed_until: str | None = None  # ISO-8601


# =========================================================================
# POST /conversations/:id/toggle_priority
# =========================================================================
class ConversationTogglePriorityRequest(BaseModel):
    """Empty / null ``priority`` clears the field (Rails ``.presence``)."""

    model_config = ConfigDict(extra="ignore")

    priority: str | None = None


# =========================================================================
# POST /conversations/:id/custom_attributes
# =========================================================================
class ConversationCustomAttributesRequest(BaseModel):
    """``params.permit(custom_attributes: {})[:custom_attributes]`` —
    the body is ``{"custom_attributes": {...}}``. A missing key is
    coerced to ``{}`` in the router.
    """

    model_config = ConfigDict(extra="ignore")

    custom_attributes: dict[str, Any] | None = None


# =========================================================================
# POST /conversations/:id/update_last_seen + /unread
# =========================================================================
# Both actions take no body in Rails — leaving them unmodeled keeps the
# router explicit and avoids a phantom empty-schema turnaround.


# =========================================================================
# POST /conversations/:conv_id/messages
# =========================================================================
class MessageCreateRequest(BaseModel):
    """Body for creating a message directly (not via the conversation
    create path).

    Rails' ``MessageBuilder`` reads the params hash directly — it accepts
    the same keys as :class:`MessageInConversationCreate` plus
    ``campaign_id`` + ``template_params`` (which land on
    ``message.additional_attributes``). ``external_created_at`` (ISO-8601
    string) allows an importer / webhook to back-date.
    """

    model_config = ConfigDict(extra="ignore")

    content: str | None = None
    message_type: str = "outgoing"
    content_type: str | None = None
    content_attributes: dict[str, Any] | None = None
    additional_attributes: dict[str, Any] | None = None
    private: bool = False
    source_id: str | None = None
    echo_id: str | None = None
    attachments: list[dict[str, Any]] | None = None
    campaign_id: int | None = None
    template_params: dict[str, Any] | None = None
    external_created_at: str | None = None  # ISO-8601
    cc_emails: str | None = None
    bcc_emails: str | None = None
    to_emails: str | None = None


# =========================================================================
# PATCH /conversations/:conv_id/messages/:id
# =========================================================================
class MessageUpdateRequest(BaseModel):
    """Rails ``permitted_params`` = ``[:id, :target_language, :status, :external_error]``.

    ``status`` expects the string enum (``sent``/``delivered``/``read``/``failed``).
    ``external_error`` is a free-form string surfaced by external gateways.
    API-inbox-only (the router enforces that before calling the service).
    """

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    external_error: str | None = None


__all__ = [
    "ConversationCreateRequest",
    "ConversationCustomAttributesRequest",
    "ConversationTogglePriorityRequest",
    "ConversationToggleStatusRequest",
    "ConversationUpdateRequest",
    "MessageCreateRequest",
    "MessageInConversationCreate",
    "MessageUpdateRequest",
]
