"""Request bodies for the inboxes + inbox_members endpoints.

Rails uses strong params (``params.permit(...)``) with an untyped Hash at
the wire. We model the same shape with Pydantic so the FastAPI router can
enforce type coercion before the builder runs.

Unknown keys are silently dropped — matches Rails' permit(-only-allowed)
behaviour. We don't fail hard on unexpected keys because Chatwoot doesn't.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# POST / PATCH /api/v1/accounts/:id/inboxes
# ---------------------------------------------------------------------------
class ChannelCreate(BaseModel):
    """The ``channel:`` sub-hash in ``POST /inboxes``.

    ``type`` is the short tag (``"api"``, ``"telegram"``, ``"whatsapp"``,
    ``"sms"``, ``"twilio_sms"``, ``"email"``, ``"web_widget"``,
    ``"facebook"``, ``"instagram"``). ``extra="allow"`` lets the
    per-channel fields (``bot_token``, ``phone_number``, ``provider_config``,
    ``account_sid``, …) flow through to :class:`InboxBuilder`, which
    validates the required set per channel type. Mirrors Rails' permissive
    ``params.permit`` on the channel sub-hash; unknown keys are harmless
    because the builder only reads the ones it knows.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    webhook_url: str | None = None
    hmac_mandatory: bool | None = None
    additional_attributes: dict[str, Any] | None = None
    # Channel::Email branding. Empty string is a real value here — it is
    # how a signature is cleared — so these are only dropped when absent.
    signature: str | None = None
    logo_url: str | None = None
    # Channel::Email transport.
    imap_enabled: bool | None = None
    imap_address: str | None = None
    imap_port: int | None = None
    imap_login: str | None = None
    imap_password: str | None = None
    imap_enable_ssl: bool | None = None
    smtp_enabled: bool | None = None
    smtp_address: str | None = None
    smtp_port: int | None = None
    smtp_login: str | None = None
    smtp_password: str | None = None
    smtp_enable_ssl_tls: bool | None = None
    smtp_enable_starttls_auto: bool | None = None


class InboxCreateRequest(BaseModel):
    """``inbox_attributes`` + ``channel`` sub-hash, matching
    ``InboxesController#permitted_params``.

    The empty-default dict pattern on optional mutable fields is safe
    because Pydantic v2 deep-copies model defaults.
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    channel: ChannelCreate

    # inbox_attributes (optional)
    greeting_enabled: bool | None = None
    greeting_message: str | None = None
    enable_email_collect: bool | None = None
    csat_survey_enabled: bool | None = None
    enable_auto_assignment: bool | None = None
    working_hours_enabled: bool | None = None
    out_of_office_message: str | None = None
    timezone: str | None = None
    allow_messages_after_resolved: bool | None = None
    lock_to_single_conversation: bool | None = None
    portal_id: int | None = None
    sender_name_type: Literal["friendly", "professional"] | None = None
    business_name: str | None = None
    csat_config: dict[str, Any] | None = None


class ChannelUpdate(BaseModel):
    """``channel:`` sub-hash on PATCH — Channel::Api EDITABLE_ATTRS.

    Other channels have different editable sets; we'll gate on the inbox's
    ``channel_type`` at the service layer when they arrive.
    """

    model_config = ConfigDict(extra="ignore")

    webhook_url: str | None = None
    hmac_mandatory: bool | None = None
    additional_attributes: dict[str, Any] | None = None
    # Channel::Email branding. Empty string is a real value here — it is
    # how a signature is cleared — so these are only dropped when absent.
    signature: str | None = None
    logo_url: str | None = None
    # Channel::Email transport.
    imap_enabled: bool | None = None
    imap_address: str | None = None
    imap_port: int | None = None
    imap_login: str | None = None
    imap_password: str | None = None
    imap_enable_ssl: bool | None = None
    smtp_enabled: bool | None = None
    smtp_address: str | None = None
    smtp_port: int | None = None
    smtp_login: str | None = None
    smtp_password: str | None = None
    smtp_enable_ssl_tls: bool | None = None
    smtp_enable_starttls_auto: bool | None = None


class InboxUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    greeting_enabled: bool | None = None
    greeting_message: str | None = None
    enable_email_collect: bool | None = None
    csat_survey_enabled: bool | None = None
    enable_auto_assignment: bool | None = None
    working_hours_enabled: bool | None = None
    out_of_office_message: str | None = None
    timezone: str | None = None
    allow_messages_after_resolved: bool | None = None
    lock_to_single_conversation: bool | None = None
    portal_id: int | None = None
    sender_name_type: Literal["friendly", "professional"] | None = None
    business_name: str | None = None
    csat_config: dict[str, Any] | None = None
    channel: ChannelUpdate | None = None


# ---------------------------------------------------------------------------
# inbox_members endpoints
# ---------------------------------------------------------------------------
class InboxMembersBody(BaseModel):
    """Body for POST/PATCH/DELETE ``/inbox_members``.

    Chatwoot accepts ``user_ids: [1, 2, 3]`` on all three verbs; DELETE
    also takes the array (quirk of Rails strong-params: verbs carry JSON
    bodies just fine).
    """

    model_config = ConfigDict(extra="ignore")

    inbox_id: int | None = None  # accepted for parity, but we take it from the path
    user_ids: list[int]
