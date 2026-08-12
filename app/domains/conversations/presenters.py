"""Wire-shape renderers for Conversation, Message, Attachment.

Ports from:
  reference/chatwoot/app/views/api/v1/conversations/partials/_conversation.json.jbuilder
  reference/chatwoot/app/views/api/v1/models/_message.json.jbuilder
  reference/chatwoot/app/models/message.rb      (push_event_data, conversation_push_event_data)
  reference/chatwoot/app/models/attachment.rb   (push_event_data, metadata_for_file_type)
  reference/chatwoot/app/models/conversation.rb (assigned_entity, cached_label_list_array)
  reference/chatwoot/app/views/api/v1/accounts/conversations/{index,show,toggle_status,messages/*}.json.jbuilder

Chatwoot emits integer unix timestamps for most datetimes and a FLOAT unix
timestamp for ``conversation.updated_at`` (``.to_f`` specifically). Both
shapes are preserved below so a byte-for-byte diff against the Rails app
passes.

Quirks the presenter reproduces deliberately (NOT bugs):

* ``message.message_type`` is emitted as the **integer** value
  (``message_type_before_type_cast`` in Rails), while
  ``message.content_type`` and ``message.status`` and
  ``conversation.status`` / ``priority`` are emitted as **strings**
  (Rails enum default).
* ``attachment.file_type`` in the push_event_data base dict is emitted
  as the enum **string** key (``:image`` → ``"image"``).
* ``conversation.id`` on the wire is ``display_id`` (per-account sequence),
  not the primary key — Chatwoot's public contract.
* ``conversation.updated_at`` is ``to_f`` (float unix seconds with
  fractional microseconds), but every other timestamp is ``to_i``.
* ``meta.hmac_verified`` comes from ``conversation.contact_inbox``; if
  the contact_inbox is absent (``destroy``'d), the key emits ``nil``.

Phase 4a-only placeholders (noted inline):
  * ``avatar_url`` → empty string (Avatarable concern arrives Phase 6+).
  * agent ``availability_status`` → ``"offline"`` (needs live presence).
  * ``cached_label_list_array`` / ``labels`` → empty list until Phase 6
    wires Labels.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.core.storage import object_url
from app.domains.conversations.models import (
    FILE_TYPE_AUDIO,
    FILE_TYPE_CONTACT,
    FILE_TYPE_EMBED,
    FILE_TYPE_FALLBACK,
    FILE_TYPE_LOCATION,
    SENDER_TYPE_AGENT_BOT,
    SENDER_TYPE_CONTACT,
    SENDER_TYPE_USER,
    Attachment,
    Conversation,
    Message,
    content_type_to_str,
    conversation_priority_to_str,
    conversation_status_to_str,
    file_type_to_str,
    message_status_to_str,
)

if TYPE_CHECKING:
    from app.domains.contacts.models import Contact
    from app.domains.teams.models import Team
    from app.domains.users.models import User


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------
def _unix(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    return int(dt.timestamp())


def _unix_or_zero(dt: datetime | None) -> int:
    """Rails ``nil.to_i == 0`` — the ``_conversation.json.jbuilder``
    emits ``0`` for unset timestamps via ``conversation.attr.to_i``.
    """
    if dt is None:
        return 0
    return int(dt.timestamp())


def _unix_float(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    return dt.timestamp()


# ---------------------------------------------------------------------------
# Sender push_event_data
# ---------------------------------------------------------------------------
def _contact_push_event_data(contact: Contact) -> dict[str, Any]:
    """Mirror of ``Contact#push_event_data``."""
    return {
        "additional_attributes": contact.additional_attributes or {},
        "custom_attributes": contact.custom_attributes or {},
        "email": contact.email,
        "id": contact.id,
        "identifier": contact.identifier,
        "name": contact.name,
        "phone_number": contact.phone_number,
        "thumbnail": "",  # Avatarable concern, Phase 6+
        "blocked": contact.blocked,
        "type": "contact",
    }


def _user_push_event_data(user: User) -> dict[str, Any]:
    """Mirror of ``User#push_event_data``."""
    return {
        "id": user.id,
        "name": user.name,
        "available_name": user.display_name or user.name,
        "avatar_url": "",  # Avatarable concern, Phase 6+
        "type": "user",
        "availability_status": "offline",  # live presence, Phase 4b+
        "thumbnail": "",
    }


def _sender_push_event_data(
    sender_type: str | None,
    sender: Any,
) -> dict[str, Any] | None:
    """Polymorphic dispatch for the ``sender`` field.

    Returns ``None`` when the message has no sender (activity messages,
    orphaned incoming messages from bots, etc.). AgentBot falls back to
    the user shape in Phase 4a — the real ``AgentBot#push_event_data``
    arrives in Phase 8.
    """
    if sender is None or sender_type is None:
        return None
    if sender_type == SENDER_TYPE_CONTACT:
        return _contact_push_event_data(sender)
    if sender_type == SENDER_TYPE_USER:
        return _user_push_event_data(sender)
    if sender_type == SENDER_TYPE_AGENT_BOT:
        # AgentBot-specific presenter arrives in Phase 8. Emit the same
        # shape as a User so the frontend doesn't crash on unknown types.
        return _user_push_event_data(sender)
    return None


# ---------------------------------------------------------------------------
# Attachment
# ---------------------------------------------------------------------------
def _attachment_base_data(att: Attachment) -> dict[str, Any]:
    """``Attachment#base_data`` mirror."""
    return {
        "id": att.id,
        "message_id": att.message_id,
        "file_type": file_type_to_str(att.file_type),
        "account_id": att.account_id,
    }


def _attachment_read_url(att: Attachment) -> str | None:
    """Browser-facing URL for the attachment blob.

    Objects in our own store are served through the authenticated media
    proxy (``attachments_router``) — the store itself is internal-only, so a
    pre-signed ``localhost`` URL wouldn't load in the browser. External URLs
    (a location map link, legacy direct links) pass through unchanged.
    """
    if not att.external_url:
        return att.external_url
    if att.external_url.startswith(object_url("")):
        return (
            f"/api/backend/api/v1/accounts/{att.account_id}"
            f"/attachments/{att.id}"
        )
    return att.external_url


def _attachment_metadata(att: Attachment) -> dict[str, Any]:
    """``Attachment#metadata_for_file_type`` mirror.

    Blob URLs point at the authenticated media proxy (see
    :func:`_attachment_read_url`); location/contact carry their coordinates
    / card metadata.
    """
    ft = att.file_type
    read_url = _attachment_read_url(att)
    if ft == FILE_TYPE_LOCATION:
        return {
            "coordinates_lat": att.coordinates_lat,
            "coordinates_long": att.coordinates_long,
            "fallback_title": att.fallback_title,
            "data_url": read_url,
        }
    if ft == FILE_TYPE_FALLBACK:
        return {
            "fallback_title": att.fallback_title,
            "data_url": read_url,
        }
    if ft == FILE_TYPE_CONTACT:
        return {
            "fallback_title": att.fallback_title,
            "meta": att.meta or {},
        }
    if ft == FILE_TYPE_EMBED:
        return {"data_url": read_url}
    if ft == FILE_TYPE_AUDIO:
        # Audio merges base_data + file_metadata + transcribed_text.
        # Phase 4a has no blob pipeline, so the file_metadata half
        # falls through to the external_url branch.
        meta = att.meta or {}
        return {
            "extension": att.extension,
            "data_url": read_url,
            "thumb_url": "",
            "transcribed_text": meta.get("transcribed_text", ""),
        }
    # image / video / file / share / story_mention / ig_* — default branch.
    return {
        "data_url": read_url,
        "thumb_url": "",
    }


def present_attachment_push_event(att: Attachment) -> dict[str, Any]:
    """Mirror of ``Attachment#push_event_data`` — returns ``None`` for
    unset ``file_type`` in Ruby, but our column is non-null with a
    server default, so we always emit a dict.
    """
    return {**_attachment_base_data(att), **_attachment_metadata(att)}


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------
def present_message(
    message: Message,
    *,
    echo_id: str | None = None,
) -> dict[str, Any]:
    """Mirror of ``_message.json.jbuilder``.

    ``echo_id`` is a Rails ``attr_accessor`` transient — it's NOT stored
    on the model, only echoed back on the create response + the push
    event to let the widget match an optimistic render to its server
    confirmation. Callers pass it through from the request body.
    """
    body: dict[str, Any] = {
        "id": message.id,
        "content": message.content,
        "inbox_id": message.inbox_id,
    }
    if echo_id:
        body["echo_id"] = echo_id
    body.update(
        {
            # ``conversation_id`` on the wire is display_id (per-account).
            "conversation_id": (
                message.conversation.display_id if message.conversation else None
            ),
            # ``message_type_before_type_cast`` — the INTEGER value.
            "message_type": message.message_type,
            "content_type": content_type_to_str(message.content_type),
            "status": message_status_to_str(message.status),
            "content_attributes": message.content_attributes or {},
            "created_at": _unix(message.created_at),
            "private": message.private,
            "source_id": message.source_id,
        }
    )
    sender_block = _sender_push_event_data(message.sender_type, _resolve_sender(message))
    if sender_block is not None:
        body["sender"] = sender_block
    if message.attachments:
        body["attachments"] = [present_attachment_push_event(a) for a in message.attachments]
    return body


def present_message_push_event(
    message: Message,
    *,
    echo_id: str | None = None,
) -> dict[str, Any]:
    """Mirror of ``Message#push_event_data`` — the fatter version used
    inside conversation ``messages[]`` and ``last_non_activity_message``.

    Starts from ``attributes.symbolize_keys`` (every column verbatim) and
    layers on: int-unix ``created_at``, integer ``message_type``,
    display-id ``conversation_id``, nested ``conversation`` summary,
    ``echo_id`` (when present), ``attachments[]``, ``sender`` block.
    """
    data: dict[str, Any] = {
        "id": message.id,
        "content": message.content,
        "account_id": message.account_id,
        "inbox_id": message.inbox_id,
        "conversation_id": (
            message.conversation.display_id if message.conversation else None
        ),
        "message_type": message.message_type,
        "created_at": _unix(message.created_at),
        "updated_at": _unix(message.updated_at),
        "private": message.private,
        "status": message_status_to_str(message.status),
        "source_id": message.source_id,
        "content_type": content_type_to_str(message.content_type),
        "content_attributes": message.content_attributes or {},
        "sender_type": message.sender_type,
        "sender_id": message.sender_id,
        "external_source_ids": message.external_source_ids or {},
        "additional_attributes": message.additional_attributes or {},
        "processed_message_content": message.processed_message_content,
        "sentiment": message.sentiment or {},
        "conversation": (
            _conversation_push_event_data(message.conversation)
            if message.conversation
            else None
        ),
    }
    if echo_id:
        data["echo_id"] = echo_id
    if message.attachments:
        data["attachments"] = [present_attachment_push_event(a) for a in message.attachments]
    sender_block = _sender_push_event_data(message.sender_type, _resolve_sender(message))
    if sender_block is not None:
        data["sender"] = sender_block
    return data


def _resolve_sender(message: Message) -> Any:
    """Best-effort sender lookup.

    Rails has a polymorphic ``belongs_to :sender``; SQLAlchemy doesn't,
    so the service layer attaches the resolved sender onto the instance
    as a non-ORM attribute (``message._resolved_sender``) when it knows
    it. When absent, the presenter emits no ``sender`` block — the
    jbuilder does ``if message.sender`` so null-sender messages drop
    the key entirely.
    """
    return getattr(message, "_resolved_sender", None)


# ---------------------------------------------------------------------------
# Conversation nested summary (Message#conversation_push_event_data)
# ---------------------------------------------------------------------------
def _conversation_push_event_data(conv: Conversation) -> dict[str, Any]:
    """Tight summary of a Conversation embedded inside a Message push event.

    Mirrors ``Message#conversation_push_event_data``. ``unread_count``
    is Chatwoot's ``unread_incoming_messages.count`` — N incoming messages
    since ``agent_last_seen_at``, capped at 10 by the Rails scope. In the
    presenter we compute it from the already-loaded ``messages`` collection
    to avoid an N+1 query.
    """
    return {
        "assignee_id": conv.assignee_id,
        "unread_count": _unread_incoming_count(conv),
        "last_activity_at": _unix(conv.last_activity_at),
        "contact_inbox": (
            {"source_id": conv.contact_inbox.source_id}
            if conv.contact_inbox is not None
            else {"source_id": None}
        ),
    }


def _unread_incoming_count(conv: Conversation) -> int:
    """Count incoming messages after ``agent_last_seen_at``, cap 10.

    Uses the already-loaded ``messages`` collection. When
    ``agent_last_seen_at`` is null, every incoming message is "unread".
    """
    from app.domains.conversations.models import MESSAGE_TYPE_INCOMING

    cutoff = conv.agent_last_seen_at
    total = 0
    for m in conv.messages or []:
        if m.message_type != MESSAGE_TYPE_INCOMING:
            continue
        if cutoff is None or (m.created_at and m.created_at > cutoff):
            total += 1
            if total >= 10:
                break
    return total


# ---------------------------------------------------------------------------
# Conversation — meta sub-block
# ---------------------------------------------------------------------------
def _present_team(team: Team) -> dict[str, Any]:
    """Mirror of ``_team.json.jbuilder``.

    The ``is_member`` key needs ``Current.user`` — we can't compute it
    in the presenter without threading the caller through, so we default
    to ``False``. When the conversations router knows the caller, it can
    override this by post-processing. Phase 4a keeps it simple.
    """
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "allow_auto_assign": team.allow_auto_assign,
        "account_id": team.account_id,
        "is_member": False,
    }


def _present_conversation_meta(conv: Conversation) -> dict[str, Any]:
    """Mirror of the ``meta`` block in ``_conversation.json.jbuilder``."""
    meta: dict[str, Any] = {
        "sender": _contact_push_event_data(conv.contact) if conv.contact else None,
        "channel": conv.inbox.channel_type if conv.inbox else None,
    }
    # assigned_entity: AgentBot takes precedence over User.
    if conv.assignee_agent_bot_id is not None:
        # Phase 4a stub — real AgentBot presenter arrives in Phase 8.
        meta["assignee"] = {"id": conv.assignee_agent_bot_id, "name": None}
        meta["assignee_type"] = "AgentBot"
    elif conv.assignee is not None:
        meta["assignee"] = _user_push_event_data(conv.assignee)
        meta["assignee_type"] = "User"
    if conv.team is not None:
        meta["team"] = _present_team(conv.team)
    meta["hmac_verified"] = (
        conv.contact_inbox.hmac_verified if conv.contact_inbox is not None else None
    )
    return meta


# ---------------------------------------------------------------------------
# Conversation — top-level
# ---------------------------------------------------------------------------
def _cached_label_list_array(conv: Conversation) -> list[str]:
    """Mirror of ``Conversation#cached_label_list_array`` — split CSV on
    ``,`` and strip whitespace. Returns ``[]`` when null.
    """
    raw = conv.cached_label_list
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _last_message_with_account_scope(conv: Conversation) -> Message | None:
    """Equivalent of
    ``conversation.messages.where(account_id: conversation.account_id).last``.
    Messages are already loaded + ordered by ``created_at`` via the
    Conversation.messages relationship.
    """
    if not conv.messages:
        return None
    same_account = [m for m in conv.messages if m.account_id == conv.account_id]
    return same_account[-1] if same_account else None


def _last_non_activity_message(conv: Conversation) -> Message | None:
    """Latest non-activity message scoped to ``account_id``. Ordered
    DESC in Rails via ``non_activity_messages``; we just grab the tail
    of the already-loaded ascending list.
    """
    from app.domains.conversations.models import MESSAGE_TYPE_ACTIVITY

    if not conv.messages:
        return None
    for m in reversed(conv.messages):
        if m.account_id != conv.account_id:
            continue
        if m.message_type == MESSAGE_TYPE_ACTIVITY:
            continue
        return m
    return None


def present_conversation(conv: Conversation) -> dict[str, Any]:
    """Mirror of ``_conversation.json.jbuilder``.

    Emits a superset of keys matching Chatwoot v4.13.0 verbatim. Nothing
    is conditionally omitted — the jbuilder writes ``null`` for missing
    values rather than dropping the key. Key order matches the jbuilder
    for ease of visual diffing but JSON consumers shouldn't rely on it.
    """
    last_msg = _last_message_with_account_scope(conv)
    last_non_activity = _last_non_activity_message(conv)
    body: dict[str, Any] = {
        "meta": _present_conversation_meta(conv),
        "id": conv.display_id,
        "messages": (
            [present_message_push_event(last_msg)] if last_msg is not None else []
        ),
        "account_id": conv.account_id,
        "uuid": str(conv.uuid) if conv.uuid else None,
        "additional_attributes": conv.additional_attributes or {},
        "agent_last_seen_at": _unix_or_zero(conv.agent_last_seen_at),
        "assignee_last_seen_at": _unix_or_zero(conv.assignee_last_seen_at),
        "can_reply": conv.can_reply(),
        "contact_last_seen_at": _unix_or_zero(conv.contact_last_seen_at),
        "custom_attributes": conv.custom_attributes or {},
        "inbox_id": conv.inbox_id,
        "labels": _cached_label_list_array(conv),
        "muted": _is_muted(conv),
        "snoozed_until": conv.snoozed_until.isoformat() if conv.snoozed_until else None,
        "status": conversation_status_to_str(conv.status),
        "created_at": _unix_or_zero(conv.created_at),
        # NOTE: updated_at is ``.to_f`` in Chatwoot — FLOAT unix seconds,
        # every other timestamp is ``.to_i``. Don't "normalise" this.
        "updated_at": _unix_float(conv.updated_at),
        "timestamp": _unix_or_zero(conv.last_activity_at),
        "first_reply_created_at": _unix_or_zero(conv.first_reply_created_at),
        "unread_count": _unread_incoming_count(conv),
        "last_non_activity_message": (
            present_message_push_event(last_non_activity)
            if last_non_activity is not None
            else None
        ),
        "last_activity_at": _unix_or_zero(conv.last_activity_at),
        "priority": conversation_priority_to_str(conv.priority),
        "waiting_since": _unix_or_zero(conv.waiting_since),
        "sla_policy_id": conv.sla_policy_id,
        # AloStudio extension (no Chatwoot equivalent): which Meta ad this
        # conversation came from, or null. Additive, so a Chatwoot client
        # that ignores unknown keys is unaffected.
        "ad_referral": _present_ad_referral(conv),
    }
    return body


def _present_ad_referral(conv: Conversation) -> dict[str, Any] | None:
    """The ad attribution block, or ``None`` when the chat wasn't from an ad.

    ``null`` rather than an empty object so the UI can branch on presence
    without inspecting the fields.
    """
    if not (conv.ad_id or conv.ad_source):
        return None
    return {
        "source": conv.ad_source,
        "ad_id": conv.ad_id,
        "headline": conv.ad_headline,
        "click_id": conv.ad_click_id,
        "captured_at": _unix_or_zero(conv.ad_captured_at),
    }


def _is_muted(conv: Conversation) -> bool:
    """Mirror of ``Conversation#muted?`` via ``ConversationMuteHelpers``:
    ``contact&.blocked? || false``.
    """
    if conv.contact is None:
        return False
    return bool(conv.contact.blocked)


# ---------------------------------------------------------------------------
# Collection envelopes
# ---------------------------------------------------------------------------
def present_conversations_index(
    conversations: list[Conversation],
    *,
    mine_count: int,
    assigned_count: int,
    unassigned_count: int,
    all_count: int,
) -> dict[str, Any]:
    """Mirror of ``accounts/conversations/index.json.jbuilder`` —
    ``{"data": {"meta": {...counts...}, "payload": [conversation...]}}``.
    """
    return {
        "data": {
            "meta": {
                "mine_count": mine_count,
                "assigned_count": assigned_count,
                "unassigned_count": unassigned_count,
                "all_count": all_count,
            },
            "payload": [present_conversation(c) for c in conversations],
        }
    }


def present_conversation_show(conv: Conversation) -> dict[str, Any]:
    """Mirror of ``accounts/conversations/show.json.jbuilder`` — top-level
    is the conversation itself (no envelope).
    """
    return present_conversation(conv)


def present_conversation_create(conv: Conversation) -> dict[str, Any]:
    """``accounts/conversations/create.json.jbuilder`` renders the show
    partial verbatim — same shape.
    """
    return present_conversation(conv)


def present_conversation_toggle_status(
    conv: Conversation,
    *,
    success: bool,
) -> dict[str, Any]:
    """Mirror of ``toggle_status.json.jbuilder``."""
    return {
        "meta": {},
        "payload": {
            "success": success,
            "conversation_id": conv.display_id,
            "current_status": conversation_status_to_str(conv.status),
            "snoozed_until": (
                conv.snoozed_until.isoformat() if conv.snoozed_until else None
            ),
        },
    }


def present_conversations_meta(
    *,
    mine_count: int,
    assigned_count: int,
    unassigned_count: int,
    all_count: int,
) -> dict[str, Any]:
    """Mirror of ``accounts/conversations/meta.json.jbuilder``."""
    return {
        "meta": {
            "mine_count": mine_count,
            "assigned_count": assigned_count,
            "unassigned_count": unassigned_count,
            "all_count": all_count,
        }
    }


# ---------------------------------------------------------------------------
# Messages index / create
# ---------------------------------------------------------------------------
def present_messages_index(
    messages: list[Message],
    *,
    conversation: Conversation,
) -> dict[str, Any]:
    """Mirror of ``accounts/conversations/messages/index.json.jbuilder``.

    ``meta`` nests a partial contact + optional assignee using
    ``push_event_data`` (fat) shape, plus raw datetimes
    (``agent_last_seen_at`` / ``assignee_last_seen_at`` — NOT ``to_i``'d
    at this layer in Rails, so we emit ISO-8601 which matches Rails'
    default timestamp serialisation).
    """
    meta: dict[str, Any] = {
        "labels": _cached_label_list_array(conversation),
        "additional_attributes": conversation.additional_attributes or {},
        "contact": (
            _contact_push_event_data(conversation.contact)
            if conversation.contact
            else None
        ),
        "agent_last_seen_at": (
            conversation.agent_last_seen_at.isoformat()
            if conversation.agent_last_seen_at
            else None
        ),
        "assignee_last_seen_at": (
            conversation.assignee_last_seen_at.isoformat()
            if conversation.assignee_last_seen_at
            else None
        ),
    }
    if conversation.assignee is not None:
        meta["assignee"] = _user_push_event_data(conversation.assignee)
    return {
        "meta": meta,
        "payload": [present_message(m) for m in messages],
    }


def present_message_create(
    message: Message,
    *,
    echo_id: str | None = None,
) -> dict[str, Any]:
    """Mirror of ``accounts/conversations/messages/create.json.jbuilder``.

    The Rails template renders ``_message.json.jbuilder`` at the top
    level — no envelope.
    """
    return present_message(message, echo_id=echo_id)


__all__ = [
    "present_attachment_push_event",
    "present_conversation",
    "present_conversation_create",
    "present_conversation_show",
    "present_conversation_toggle_status",
    "present_conversations_index",
    "present_conversations_meta",
    "present_message",
    "present_message_create",
    "present_message_push_event",
    "present_messages_index",
]
