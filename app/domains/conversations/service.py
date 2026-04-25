"""Conversation + Message services.

Ported from:
  reference/chatwoot/app/builders/conversation_builder.rb
  reference/chatwoot/app/builders/messages/message_builder.rb
  reference/chatwoot/app/models/conversation.rb  (state machine methods)
  reference/chatwoot/app/models/message.rb        (post-create callbacks)

Phase 4a scope:

  * ``ConversationBuilder``    — create or reuse-latest when inbox
    ``lock_to_single_conversation`` is true.
  * ``MessageBuilder``          — create a message + its Attachments,
    apply API-channel-only validation (``incoming`` requires API inbox),
    echo back ``echo_id`` and ``source_id`` on the wire.
  * ``toggle_status`` / ``toggle_priority`` / ``bot_handoff`` — mirror
    Chatwoot's state machine methods.
  * ``apply_message_post_create`` — the Rails
    ``execute_after_create_commit_callbacks`` cascade, minus:
      - liquid email rendering (Phase 5b)
      - SendReplyJob          (Phase 4b — realtime + job queue)
      - MessageTemplateHooks  (Phase 5)
      - searchkick re-index   (Phase 10)
    What stays:
      - ``reopen_conversation`` (snoozed/resolved → open on incoming).
      - ``mark_pending_conversation_as_open_for_human_response`` (stub —
        Captain assistant not in scope, ``captain_pending_conversation?``
        is hard-coded ``False`` in Rails today anyway).
      - ``set_conversation_activity`` (bump ``last_activity_at``).
      - ``dispatch_create_events`` (no-op dispatcher → logs).
      - ``update_waiting_since`` / ``first_reply_created_at``.
      - ``update_contact_activity``.

Deferred explicitly:
  * ``AssignmentHandler`` team-scope guard (``ensure_assignee_is_from_team``)
    — Phase 4c.
  * ``AutoAssignmentHandler``                              — Phase 4c.
  * ``ActivityMessageHandler`` fan-out (priority/team/label) — Phase 4b.
  * ``validate_referer_url`` — trivial; lands with 4b.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.conversations.events import (
    CONVERSATION_BOT_HANDOFF,
    CONVERSATION_CREATED,
    CONVERSATION_OPENED,
    CONVERSATION_RESOLVED,
    CONVERSATION_STATUS_CHANGED,
    CONVERSATION_UPDATED,
    FIRST_REPLY_CREATED,
    MESSAGE_CREATED,
    REPLY_CREATED,
    dispatcher,
)
from app.domains.conversations.models import (
    CONTENT_TYPE_TEXT,
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_PENDING,
    CONVERSATION_STATUS_RESOLVED,
    CONVERSATION_STATUS_SNOOZED,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    SENDER_TYPE_CONTACT,
    SENDER_TYPE_USER,
    Attachment,
    Conversation,
    Message,
    content_type_from_str,
    conversation_priority_from_str,
    conversation_status_from_str,
    file_type_from_str,
    message_status_from_str,
    message_type_from_str,
)
from app.domains.inboxes.models import CHANNEL_TYPE_API, Inbox

# Rails' ``Limits.conversation_message_per_minute_limit`` — Chatwoot sets
# this via ``config/initializers/limits.rb`` (default 20). Mirrored here
# because it's a hard cap enforced in the model's ``before_validation``.
CONVERSATION_MESSAGE_PER_MINUTE_LIMIT = 20

# Rails ``Message::NUMBER_OF_PERMITTED_ATTACHMENTS`` constant.
NUMBER_OF_PERMITTED_ATTACHMENTS = 15


def _utcnow() -> datetime:
    return datetime.now(UTC)


# =========================================================================
# ConversationBuilder
# =========================================================================
@dataclass
class ConversationBuilderParams:
    """Inputs for :func:`create_conversation` — mirrors the Rails
    builder's permitted params set."""

    additional_attributes: dict[str, Any] | None = None
    custom_attributes: dict[str, Any] | None = None
    status: str | None = None
    snoozed_until: datetime | None = None
    assignee_id: int | None = None
    team_id: int | None = None


async def create_conversation(
    session: AsyncSession,
    *,
    contact_inbox: ContactInbox,
    params: ConversationBuilderParams,
) -> Conversation:
    """Port of ``ConversationBuilder#perform``.

    If ``contact_inbox.inbox.lock_to_single_conversation`` is True and a
    prior conversation exists on this ContactInbox, return the latest
    one (Chatwoot's single-session-per-contact behaviour). Otherwise
    create a fresh ``Conversation`` with the builder params applied.
    """
    inbox = contact_inbox.inbox
    if inbox is None:  # defensive — should never happen when relationship is eager
        inbox = (
            await session.exec(select(Inbox).where(Inbox.id == contact_inbox.inbox_id))
        ).one()

    if inbox.lock_to_single_conversation:
        prior = (
            await session.exec(
                select(Conversation)
                .where(Conversation.contact_inbox_id == contact_inbox.id)
                .order_by(Conversation.id.desc())  # type: ignore[attr-defined]
                .limit(1)
            )
        ).first()
        if prior is not None:
            return prior

    status_int: int = CONVERSATION_STATUS_OPEN
    if params.status is not None:
        status_int = conversation_status_from_str(params.status)

    conv = Conversation(
        account_id=inbox.account_id,
        inbox_id=contact_inbox.inbox_id,
        contact_id=contact_inbox.contact_id,
        contact_inbox_id=contact_inbox.id,
        additional_attributes=params.additional_attributes or {},
        custom_attributes=params.custom_attributes or {},
        status=status_int,
        snoozed_until=params.snoozed_until,
        assignee_id=params.assignee_id,
        team_id=params.team_id,
        last_activity_at=_utcnow(),
        waiting_since=_utcnow(),  # mirrors ``ensure_waiting_since`` before_create
    )
    session.add(conv)
    await session.flush()
    # ``display_id`` + ``uuid`` are server-assigned; refresh to pull them.
    await session.refresh(conv)

    await dispatcher.dispatch(session, CONVERSATION_CREATED, conversation=conv)
    return conv


# =========================================================================
# State-machine methods
# =========================================================================
async def toggle_status(
    session: AsyncSession,
    *,
    conversation: Conversation,
    status: str | None = None,
    snoozed_until: datetime | None = None,
) -> Conversation:
    """Port of ``Conversation#toggle_status`` + the controller's
    ``toggle_status`` action, which accepts an optional ``status`` kwarg
    plus a ``snoozed_until`` datetime.

    Semantics (from the Ruby ``toggle_status`` method + controller):

      * No ``status`` param and the conversation is ``open``       → resolved
      * No ``status`` param and the conversation is ``resolved``   → open
      * No ``status`` param and ``pending`` or ``snoozed``         → open
      * ``status='snoozed'`` + ``snoozed_until`` datetime           → snoozed
      * ``status=<anything>`` just sets that status.

    Side-effects:
      * ``waiting_since`` is cleared on resolve (parity with
        ``handle_resolved_status_change``).
      * ``snoozed_until`` is cleared when the new status is not snoozed
        (parity with ``ensure_snooze_until_reset``).
      * Dispatches ``CONVERSATION_OPENED``, ``CONVERSATION_RESOLVED``,
        ``CONVERSATION_STATUS_CHANGED``.
    """
    prev_status = conversation.status

    if status is None:
        # Toggle without explicit target — mirror Ruby `toggle_status`.
        if conversation.status == CONVERSATION_STATUS_OPEN:
            new_status = CONVERSATION_STATUS_RESOLVED
        else:
            new_status = CONVERSATION_STATUS_OPEN
    else:
        new_status = conversation_status_from_str(status)

    conversation.status = new_status
    if new_status == CONVERSATION_STATUS_SNOOZED:
        conversation.snoozed_until = snoozed_until
    else:
        conversation.snoozed_until = None

    if new_status == CONVERSATION_STATUS_RESOLVED:
        conversation.waiting_since = None

    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)

    changed = prev_status != new_status
    if changed:
        await dispatcher.dispatch(
            session, CONVERSATION_STATUS_CHANGED, conversation=conversation
        )
        if new_status == CONVERSATION_STATUS_OPEN:
            await dispatcher.dispatch(
                session, CONVERSATION_OPENED, conversation=conversation
            )
        elif new_status == CONVERSATION_STATUS_RESOLVED:
            await dispatcher.dispatch(
                session, CONVERSATION_RESOLVED, conversation=conversation
            )
        await dispatcher.dispatch(
            session,
            CONVERSATION_UPDATED,
            conversation=conversation,
            changed_attributes={"status": [prev_status, new_status]},
        )
    return conversation


async def toggle_priority(
    session: AsyncSession,
    *,
    conversation: Conversation,
    priority: str | None,
) -> Conversation:
    """Port of ``Conversation#toggle_priority``.

    ``priority=None`` clears the priority (matches Rails' ``.presence``
    nil-coerce on blank strings).
    """
    prev = conversation.priority
    conversation.priority = conversation_priority_from_str(priority)
    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)
    if prev != conversation.priority:
        await dispatcher.dispatch(
            session,
            CONVERSATION_UPDATED,
            conversation=conversation,
            changed_attributes={"priority": [prev, conversation.priority]},
        )
    return conversation


async def bot_handoff(
    session: AsyncSession, *, conversation: Conversation
) -> Conversation:
    """Port of ``Conversation#bot_handoff!``.

    Opens the conversation and stamps ``waiting_since`` if blank.
    """
    if conversation.waiting_since is None:
        conversation.waiting_since = _utcnow()
    conversation.status = CONVERSATION_STATUS_OPEN
    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)
    await dispatcher.dispatch(session, CONVERSATION_BOT_HANDOFF, conversation=conversation)
    return conversation


async def update_custom_attributes(
    session: AsyncSession,
    *,
    conversation: Conversation,
    custom_attributes: dict[str, Any],
) -> Conversation:
    """Controller endpoint: replace the ``custom_attributes`` JSONB."""
    conversation.custom_attributes = custom_attributes
    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)
    await dispatcher.dispatch(
        session,
        CONVERSATION_UPDATED,
        conversation=conversation,
        changed_attributes={"custom_attributes": [None, custom_attributes]},
    )
    return conversation


# ``reassign_conversation`` (the ``/assignments`` nested endpoint) is
# deferred to Phase 4c alongside the round-robin service — it needs the
# team-scope guard from ``AssignmentHandler`` plus proper activity-message
# dispatch that isn't worth stubbing half-way.


# =========================================================================
# MessageBuilder
# =========================================================================
@dataclass
class _AttachmentSpec:
    """Incoming attachment payload — mirrors Rails' ``@attachments``.

    Phase 4a accepts only ``external_url``-style attachments (no multipart
    file upload). The MinIO-backed upload endpoint + ActiveStorage
    equivalent land in Phase 10.
    """

    file_type: str = "file"
    external_url: str | None = None
    fallback_title: str | None = None
    coordinates_lat: float | None = None
    coordinates_long: float | None = None
    meta: dict[str, Any] | None = None
    extension: str | None = None


@dataclass
class MessageBuilderParams:
    content: str | None = None
    message_type: str = "outgoing"
    content_type: str | None = None
    content_attributes: dict[str, Any] | None = None
    additional_attributes: dict[str, Any] | None = None
    private: bool = False
    source_id: str | None = None
    echo_id: str | None = None
    sender_id: int | None = None  # for message_type='incoming' or Bot
    sender_type: str | None = None
    attachments: list[_AttachmentSpec] | None = None
    external_created_at: datetime | None = None
    campaign_id: int | None = None
    template_params: dict[str, Any] | None = None
    # cc/bcc/to only honoured for Email inboxes — Phase 5b. 4a parses
    # but stores verbatim.
    cc_emails: str | None = None
    bcc_emails: str | None = None
    to_emails: str | None = None


def _validate_message_type_for_inbox(
    *, inbox: Inbox, message_type_str: str
) -> None:
    """Port of ``MessageBuilder#message_type`` guard.

    Rails raises ``StandardError`` directly, the controller converts to
    422. Skip straight to 422 here.
    """
    if (
        inbox.channel_type != CHANNEL_TYPE_API
        and message_type_str == "incoming"
    ):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Incoming messages are only allowed in Api inboxes"},
        )


def _resolve_sender(
    *,
    conversation: Conversation,
    message_type_str: str,
    user_id: int | None,
) -> tuple[str | None, int | None]:
    """Mirror of ``MessageBuilder#sender``.

    For outgoing: sender is the currently authenticated User (Phase 4a
    doesn't support AgentBot senders — that's Phase 8).
    For incoming: sender is the Contact on this conversation.
    """
    if message_type_str == "outgoing":
        if user_id is None:
            return None, None
        return SENDER_TYPE_USER, user_id
    # incoming
    return SENDER_TYPE_CONTACT, conversation.contact_id


async def _apply_attachments(
    session: AsyncSession,
    *,
    message: Message,
    specs: list[_AttachmentSpec] | None,
) -> None:
    if not specs:
        return
    if len(specs) > NUMBER_OF_PERMITTED_ATTACHMENTS:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "attachments: exceeded maximum allowed"},
        )
    for spec in specs:
        att = Attachment(
            account_id=message.account_id,
            message_id=message.id,
            file_type=file_type_from_str(spec.file_type),
            external_url=spec.external_url,
            fallback_title=spec.fallback_title,
            coordinates_lat=spec.coordinates_lat or 0.0,
            coordinates_long=spec.coordinates_long or 0.0,
            meta=spec.meta,
            extension=spec.extension,
        )
        session.add(att)


async def _apply_email_fields(
    *, message: Message, inbox: Inbox, params: MessageBuilderParams
) -> None:
    """Port of ``MessageBuilder#process_emails``.

    Phase 4a stores the comma-split addresses verbatim in
    ``content_attributes`` — no SMTP validation (lands with Phase 5b).
    """
    if inbox.channel_type == CHANNEL_TYPE_API:
        return
    if inbox.channel_type != "Channel::Email":
        return

    def split(s: str | None) -> list[str]:
        if not s:
            return []
        return [part for part in s.replace(" ", "").split(",") if part]

    ca = dict(message.content_attributes or {})
    ca["cc_emails"] = split(params.cc_emails)
    ca["bcc_emails"] = split(params.bcc_emails)
    ca["to_emails"] = split(params.to_emails)
    message.content_attributes = ca


async def _enforce_flooding_cap(
    session: AsyncSession, *, conversation_id: int
) -> None:
    """Port of ``Message#prevent_message_flooding``."""
    from datetime import timedelta

    from sqlalchemy import func as sa_func

    one_min_ago = _utcnow() - timedelta(minutes=1)
    count = int(
        (
            await session.exec(  # type: ignore[call-overload]
                select(sa_func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation_id)
                .where(Message.created_at >= one_min_ago)
            )
        ).one()
        or 0
    )
    if count >= CONVERSATION_MESSAGE_PER_MINUTE_LIMIT:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Too many messages"},
        )


async def create_message(
    session: AsyncSession,
    *,
    conversation: Conversation,
    params: MessageBuilderParams,
    user_id: int | None,
) -> Message:
    """Port of ``Messages::MessageBuilder#perform`` + the subset of
    ``Message``'s post-create callbacks listed in the module docstring.

    Returns the persisted Message with attachments loaded.
    """
    inbox = conversation.inbox

    _validate_message_type_for_inbox(inbox=inbox, message_type_str=params.message_type)
    await _enforce_flooding_cap(session, conversation_id=conversation.id)

    sender_type, sender_id = _resolve_sender(
        conversation=conversation,
        message_type_str=params.message_type,
        user_id=user_id,
    )

    content_type_int = (
        content_type_from_str(params.content_type)
        if params.content_type
        else CONTENT_TYPE_TEXT
    )
    message_type_int = message_type_from_str(params.message_type)

    additional_attrs = dict(params.additional_attributes or {})
    if params.campaign_id is not None:
        additional_attrs["campaign_id"] = params.campaign_id
    if params.template_params is not None:
        additional_attrs["template_params"] = params.template_params

    content_attrs = dict(params.content_attributes or {})
    if params.external_created_at is not None:
        content_attrs["external_created_at"] = params.external_created_at.isoformat()

    processed_message_content = params.content
    if content_attrs:
        # Rails ``ensure_processed_message_content`` picks quoted email
        # text first, then raw content. Phase 4a has no quoted-email
        # logic (Phase 5b) so we just truncate ``content``.
        pass
    if processed_message_content and len(processed_message_content) > 150_000:
        processed_message_content = processed_message_content[:150_000]

    msg = Message(
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        conversation_id=conversation.id,
        sender_type=sender_type,
        sender_id=sender_id,
        message_type=message_type_int,
        content_type=content_type_int,
        content=params.content,
        processed_message_content=processed_message_content,
        content_attributes=content_attrs,
        additional_attributes=additional_attrs,
        private=params.private,
        source_id=params.source_id,
    )
    session.add(msg)
    await session.flush()

    # Email fields (no-op unless Email inbox).
    await _apply_email_fields(message=msg, inbox=inbox, params=params)

    # Attachments — needs msg.id, so flush first.
    await _apply_attachments(session, message=msg, specs=params.attachments)
    await session.flush()

    # ---- post-create callbacks ----
    await _apply_message_post_create(session, message=msg, conversation=conversation)

    await session.refresh(msg)
    # Attach the resolved polymorphic sender so the presenter can emit the
    # ``sender`` block. Rails gets this for free via ``belongs_to :sender``;
    # SQLAlchemy has no polymorphic relationship for us to lean on.
    await _attach_resolved_sender(session, message=msg, conversation=conversation)
    return msg


async def _attach_resolved_sender(
    session: AsyncSession,
    *,
    message: Message,
    conversation: Conversation,
) -> None:
    """Look up the polymorphic sender and stash it on ``message._resolved_sender``.

    The presenter reads this non-ORM attribute; Rails' ``belongs_to :sender``
    would resolve it automatically, but SQLAlchemy requires a manual lookup
    because Chatwoot uses ``sender_type``/``sender_id`` without a formal
    polymorphic association mapper.
    """
    if message.sender_type is None or message.sender_id is None:
        message._resolved_sender = None  # type: ignore[attr-defined]
        return
    if message.sender_type == SENDER_TYPE_CONTACT:
        # The conversation's contact is the only contact that can send on it.
        if conversation.contact is not None and conversation.contact.id == message.sender_id:
            message._resolved_sender = conversation.contact  # type: ignore[attr-defined]
            return
        from app.domains.contacts.models import Contact

        contact = await session.get(Contact, message.sender_id)
        message._resolved_sender = contact  # type: ignore[attr-defined]
        return
    if message.sender_type == SENDER_TYPE_USER:
        from app.domains.users.models import User

        user = await session.get(User, message.sender_id)
        message._resolved_sender = user  # type: ignore[attr-defined]
        return
    # AgentBot arrives with Phase 8 — leave resolved=None so the presenter
    # drops the sender block rather than crashing.
    message._resolved_sender = None  # type: ignore[attr-defined]


async def _apply_message_post_create(
    session: AsyncSession, *, message: Message, conversation: Conversation
) -> None:
    """Port of the subset of ``Message#execute_after_create_commit_callbacks``
    that Phase 4a ships. See module docstring for deferrals."""

    # 1. reopen_conversation -------------------------------------------
    # Rails: ``return if conversation.muted?`` — Phase 4a has no mute
    # store yet (contacts.blocked is the proxy).
    if message.message_type == MESSAGE_TYPE_INCOMING:
        if conversation.status == CONVERSATION_STATUS_SNOOZED:
            conversation.status = CONVERSATION_STATUS_OPEN
            conversation.snoozed_until = None
        elif conversation.status == CONVERSATION_STATUS_RESOLVED:
            # Rails chooses between ``pending`` (bot inbox) and ``open``
            # (API/other). ``Inbox.active_bot?`` is Phase 8 material, so
            # route everything to ``open`` in 4a.
            conversation.status = CONVERSATION_STATUS_OPEN

    # 2. set_conversation_activity -------------------------------------
    conversation.last_activity_at = message.created_at or _utcnow()
    session.add(conversation)
    await session.flush()

    # 3. dispatch_create_events + waiting_since / first_reply bookkeeping
    await dispatcher.dispatch(session, MESSAGE_CREATED, message=message)

    if _valid_first_reply(message=message, conversation=conversation):
        await dispatcher.dispatch(session, FIRST_REPLY_CREATED, message=message)
        conversation.first_reply_created_at = message.created_at
        conversation.waiting_since = None
        session.add(conversation)
        await session.flush()
    else:
        await _update_waiting_since(session, message=message, conversation=conversation)


def _is_human_response(message: Message) -> bool:
    """Port of ``Message#human_response?`` (subset).

    Phase 4a has no AgentBot or Campaigns, so ``automation_rule_id`` /
    ``campaign_id`` / ``AgentBot`` branches collapse to a simple check:
    outgoing + sender is a User.
    """
    if message.message_type != MESSAGE_TYPE_OUTGOING:
        return False
    if (message.additional_attributes or {}).get("campaign_id"):
        return False
    if (message.content_attributes or {}).get("automation_rule_id"):
        return False
    return message.sender_type == SENDER_TYPE_USER


def _valid_first_reply(*, message: Message, conversation: Conversation) -> bool:
    """Port of ``Message#valid_first_reply?``.

    4a simplification: we don't do the "≤1 prior outgoing non-bot
    message" check (requires a non-trivial query). In practice the
    ``first_reply_created_at is None`` guard already prevents the flag
    from firing twice.
    """
    if not _is_human_response(message):
        return False
    if message.private:
        return False
    if conversation.first_reply_created_at is not None:
        return False
    return True


async def _update_waiting_since(
    session: AsyncSession, *, message: Message, conversation: Conversation
) -> None:
    """Port of ``Message#update_waiting_since``."""
    changed = False
    if conversation.waiting_since is not None and not message.private:
        if _is_human_response(message):
            await dispatcher.dispatch(
                session,
                REPLY_CREATED,
                waiting_since=conversation.waiting_since,
                message=message,
            )
            conversation.waiting_since = None
            changed = True
        # bot_response branch: Phase 8
    # set_waiting_since_on_incoming_message
    if (
        message.message_type == MESSAGE_TYPE_INCOMING
        and conversation.waiting_since is None
    ):
        conversation.waiting_since = message.created_at or _utcnow()
        changed = True
    if changed:
        session.add(conversation)
        await session.flush()


# =========================================================================
# Destructive / lifecycle helpers
# =========================================================================
async def soft_delete_message(
    session: AsyncSession, *, message: Message, deleted_content: str
) -> Message:
    """Port of the controller's ``destroy`` action.

    Chatwoot doesn't actually delete the row — it overwrites
    ``content`` + sets ``content_attributes.deleted = true`` so the
    timeline keeps the activity slot. We do the same.
    """
    message.content = deleted_content
    ca = dict(message.content_attributes or {})
    ca["deleted"] = True
    message.content_attributes = ca
    session.add(message)
    await session.flush()
    await session.refresh(message)
    return message


async def update_message_status(
    session: AsyncSession,
    *,
    message: Message,
    status: str,
    external_error: str | None = None,
) -> Message:
    """Port of the controller's ``update`` action for messages (API
    inbox only)."""
    message.status = message_status_from_str(status)
    if external_error is not None:
        ca = dict(message.content_attributes or {})
        ca["external_error"] = external_error
        message.content_attributes = ca
    session.add(message)
    await session.flush()
    await session.refresh(message)
    return message


# =========================================================================
# Contact-merge closure (Phase 3 deferral)
# =========================================================================
async def reassign_mergee_conversations(
    session: AsyncSession, *, mergee_contact_id: int, base_contact_id: int
) -> None:
    """Port of the conversation/message half of
    ``ContactMergeActionService``.

    Moves every ``Conversation`` + every ``Contact``-sender ``Message``
    from the mergee contact onto the base contact. Called from
    :class:`app.domains.contacts.service.ContactMergeAction` now that
    the Phase 4 tables exist.

    ``ContactInbox`` reassignment stays in :class:`ContactMergeAction`
    (``_merge_contact_inboxes``) to keep the cross-domain responsibility
    split clean: contacts owns the ContactInbox reassignment + notes +
    the mergee delete, conversations owns conversation + message moves.
    """
    from sqlalchemy import update

    await session.exec(  # type: ignore[call-overload]
        update(Conversation)
        .where(Conversation.contact_id == mergee_contact_id)
        .values(contact_id=base_contact_id)
    )
    await session.exec(  # type: ignore[call-overload]
        update(Message)
        .where(Message.sender_type == SENDER_TYPE_CONTACT)
        .where(Message.sender_id == mergee_contact_id)
        .values(sender_id=base_contact_id)
    )
    await session.flush()


__all__ = [
    "CONVERSATION_MESSAGE_PER_MINUTE_LIMIT",
    "ConversationBuilderParams",
    "MessageBuilderParams",
    "_AttachmentSpec",
    "bot_handoff",
    "create_conversation",
    "create_message",
    "reassign_mergee_conversations",
    "soft_delete_message",
    "toggle_priority",
    "toggle_status",
    "update_custom_attributes",
    "update_message_status",
]
