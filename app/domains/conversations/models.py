"""Conversation + Message + Attachment + Mention + ConversationParticipant.

Ported from:
  reference/chatwoot/app/models/conversation.rb
  reference/chatwoot/app/models/message.rb
  reference/chatwoot/app/models/attachment.rb
  reference/chatwoot/app/models/mention.rb
  reference/chatwoot/app/models/conversation_participant.rb
  reference/chatwoot/db/schema.rb (v4.13.0)

Column-level parity notes:

* ``conversations.display_id`` is Rails-assigned via the
  ``conv_dpid_seq_<account_id>`` sequence + a ``BEFORE INSERT`` trigger
  (``increment_conversation_count``). Both the sequence creation (in
  ``accounts.after_create``) and the trigger itself move into the
  Alembic migration: computing ``display_id`` in Python can't be made
  race-safe under concurrent inserts.

* ``conversations.uuid`` is ``gen_random_uuid()`` via ``pgcrypto``.
  Rails' ``before_create :set_uuid`` is trivial; we set it via a
  ``server_default`` so both the Python factory path and a raw SQL
  ``INSERT`` land identically.

* ``conversations.status`` / ``priority`` are Rails integer enums:
    * status   → open=0, resolved=1, pending=2, snoozed=3 (default 0)
    * priority → low=0, medium=1, high=2, urgent=3 (nullable)

* ``messages.message_type`` enum: incoming=0, outgoing=1, activity=2,
  template=3.
  ``messages.content_type`` enum: 13 values (text..voice_call).
  ``messages.status`` enum: sent=0, delivered=1, read=2, failed=3.

* ``messages.sender_type`` + ``messages.sender_id`` form a
  **polymorphic association** (Rails ``belongs_to :sender, polymorphic:
  true``). Rails stores the class name verbatim in the string column —
  ``'User'``, ``'Contact'``, ``'AgentBot'``, ``'Captain::Assistant'``.
  We mirror that (no FK), so side-by-side dumps line up byte-for-byte.

* ``messages.content_attributes`` is JSON (not JSONB) in Chatwoot's
  schema — we keep JSON here to preserve ``key-order`` stability for any
  downstream diff-based parity test.

* ``attachments.external_url`` stores a direct URL; the ActiveStorage
  blob-based upload pipeline does NOT ship in Phase 4a (MinIO +
  pre-signed URL lands in Phase 10). ``file_type`` is an integer enum
  with 13 values mirroring Rails.

Deferred FKs (schema parity, no SA-level ForeignKey declared):
  * ``conversations.sla_policy_id``  — Phase 5 (SLA).
  * ``conversations.campaign_id``    — Phase 6 (Campaigns).
  * ``conversations.assignee_agent_bot_id`` — Phase 8 (AgentBot ecosystem).
  * ``messages.additional_attributes['campaign_id']`` — same.

Deferred callbacks/concerns (see app/domains/conversations/service.py):
  * ``Labelable``, ``ActivityMessageHandler`` sub-handlers
    (priority/label/SLA) — Phase 4b once dispatcher is real.
  * ``Messages::InReplyToMessageBuilder`` — needs email channel → 5b.
  * Searchkick indexing — Phase 10.

NOTE: we intentionally do NOT ``from __future__ import annotations`` in
this file. SQLModel's ``Relationship()`` forward refs (``"Account"``,
``list["Message"]``) rely on the annotation being evaluable at class-
definition time. With the future import enabled, every annotation
becomes a raw string — so ``"Account"`` turns into ``'"Account"'`` (a
string containing the quotes), which SQLAlchemy later fails to resolve
against its class registry. Same reason :mod:`app.domains.contacts.models`
skips the import.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship

from app.core.base_model import TimestampMixin

if TYPE_CHECKING:
    from app.domains.accounts.models import Account
    from app.domains.contacts.models import Contact, ContactInbox
    from app.domains.inboxes.models import Inbox
    from app.domains.teams.models import Team
    from app.domains.users.models import User


# ---------------------------------------------------------------------------
# Conversation.status enum
# ---------------------------------------------------------------------------
CONVERSATION_STATUS_OPEN = 0
CONVERSATION_STATUS_RESOLVED = 1
CONVERSATION_STATUS_PENDING = 2
CONVERSATION_STATUS_SNOOZED = 3

_STATUS_INT_TO_STR: dict[int, str] = {
    CONVERSATION_STATUS_OPEN: "open",
    CONVERSATION_STATUS_RESOLVED: "resolved",
    CONVERSATION_STATUS_PENDING: "pending",
    CONVERSATION_STATUS_SNOOZED: "snoozed",
}
_STATUS_STR_TO_INT: dict[str, int] = {v: k for k, v in _STATUS_INT_TO_STR.items()}


def conversation_status_to_str(value: int) -> str:
    return _STATUS_INT_TO_STR.get(value, "open")


def conversation_status_from_str(value: str) -> int:
    try:
        return _STATUS_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown conversation status: {value!r}") from e


# ---------------------------------------------------------------------------
# Conversation.priority enum (nullable)
# ---------------------------------------------------------------------------
CONVERSATION_PRIORITY_LOW = 0
CONVERSATION_PRIORITY_MEDIUM = 1
CONVERSATION_PRIORITY_HIGH = 2
CONVERSATION_PRIORITY_URGENT = 3

_PRIORITY_INT_TO_STR: dict[int, str] = {
    CONVERSATION_PRIORITY_LOW: "low",
    CONVERSATION_PRIORITY_MEDIUM: "medium",
    CONVERSATION_PRIORITY_HIGH: "high",
    CONVERSATION_PRIORITY_URGENT: "urgent",
}
_PRIORITY_STR_TO_INT: dict[str, int] = {v: k for k, v in _PRIORITY_INT_TO_STR.items()}


def conversation_priority_to_str(value: int | None) -> str | None:
    if value is None:
        return None
    return _PRIORITY_INT_TO_STR.get(value)


def conversation_priority_from_str(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return _PRIORITY_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown conversation priority: {value!r}") from e


# ---------------------------------------------------------------------------
# Message.message_type enum
# ---------------------------------------------------------------------------
MESSAGE_TYPE_INCOMING = 0
MESSAGE_TYPE_OUTGOING = 1
MESSAGE_TYPE_ACTIVITY = 2
MESSAGE_TYPE_TEMPLATE = 3

_MESSAGE_TYPE_INT_TO_STR: dict[int, str] = {
    MESSAGE_TYPE_INCOMING: "incoming",
    MESSAGE_TYPE_OUTGOING: "outgoing",
    MESSAGE_TYPE_ACTIVITY: "activity",
    MESSAGE_TYPE_TEMPLATE: "template",
}
_MESSAGE_TYPE_STR_TO_INT: dict[str, int] = {v: k for k, v in _MESSAGE_TYPE_INT_TO_STR.items()}


def message_type_to_str(value: int) -> str:
    return _MESSAGE_TYPE_INT_TO_STR.get(value, "incoming")


def message_type_from_str(value: str) -> int:
    try:
        return _MESSAGE_TYPE_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown message_type: {value!r}") from e


# ---------------------------------------------------------------------------
# Message.content_type enum (13 values)
# ---------------------------------------------------------------------------
CONTENT_TYPE_TEXT = 0
CONTENT_TYPE_INPUT_TEXT = 1
CONTENT_TYPE_INPUT_TEXTAREA = 2
CONTENT_TYPE_INPUT_EMAIL = 3
CONTENT_TYPE_INPUT_SELECT = 4
CONTENT_TYPE_CARDS = 5
CONTENT_TYPE_FORM = 6
CONTENT_TYPE_ARTICLE = 7
CONTENT_TYPE_INCOMING_EMAIL = 8
CONTENT_TYPE_INPUT_CSAT = 9
CONTENT_TYPE_INTEGRATIONS = 10
CONTENT_TYPE_STICKER = 11
CONTENT_TYPE_VOICE_CALL = 12

_CONTENT_TYPE_INT_TO_STR: dict[int, str] = {
    CONTENT_TYPE_TEXT: "text",
    CONTENT_TYPE_INPUT_TEXT: "input_text",
    CONTENT_TYPE_INPUT_TEXTAREA: "input_textarea",
    CONTENT_TYPE_INPUT_EMAIL: "input_email",
    CONTENT_TYPE_INPUT_SELECT: "input_select",
    CONTENT_TYPE_CARDS: "cards",
    CONTENT_TYPE_FORM: "form",
    CONTENT_TYPE_ARTICLE: "article",
    CONTENT_TYPE_INCOMING_EMAIL: "incoming_email",
    CONTENT_TYPE_INPUT_CSAT: "input_csat",
    CONTENT_TYPE_INTEGRATIONS: "integrations",
    CONTENT_TYPE_STICKER: "sticker",
    CONTENT_TYPE_VOICE_CALL: "voice_call",
}
_CONTENT_TYPE_STR_TO_INT: dict[str, int] = {v: k for k, v in _CONTENT_TYPE_INT_TO_STR.items()}


def content_type_to_str(value: int) -> str:
    return _CONTENT_TYPE_INT_TO_STR.get(value, "text")


def content_type_from_str(value: str) -> int:
    try:
        return _CONTENT_TYPE_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown content_type: {value!r}") from e


# ---------------------------------------------------------------------------
# Message.status enum
# ---------------------------------------------------------------------------
MESSAGE_STATUS_SENT = 0
MESSAGE_STATUS_DELIVERED = 1
MESSAGE_STATUS_READ = 2
MESSAGE_STATUS_FAILED = 3

_MESSAGE_STATUS_INT_TO_STR: dict[int, str] = {
    MESSAGE_STATUS_SENT: "sent",
    MESSAGE_STATUS_DELIVERED: "delivered",
    MESSAGE_STATUS_READ: "read",
    MESSAGE_STATUS_FAILED: "failed",
}
_MESSAGE_STATUS_STR_TO_INT: dict[str, int] = {v: k for k, v in _MESSAGE_STATUS_INT_TO_STR.items()}


def message_status_to_str(value: int) -> str:
    return _MESSAGE_STATUS_INT_TO_STR.get(value, "sent")


def message_status_from_str(value: str) -> int:
    try:
        return _MESSAGE_STATUS_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown message status: {value!r}") from e


# ---------------------------------------------------------------------------
# Attachment.file_type enum (13 values)
# ---------------------------------------------------------------------------
FILE_TYPE_IMAGE = 0
FILE_TYPE_AUDIO = 1
FILE_TYPE_VIDEO = 2
FILE_TYPE_FILE = 3
FILE_TYPE_LOCATION = 4
FILE_TYPE_FALLBACK = 5
FILE_TYPE_SHARE = 6
FILE_TYPE_STORY_MENTION = 7
FILE_TYPE_CONTACT = 8
FILE_TYPE_IG_REEL = 9
FILE_TYPE_IG_POST = 10
FILE_TYPE_IG_STORY = 11
FILE_TYPE_EMBED = 12

_FILE_TYPE_INT_TO_STR: dict[int, str] = {
    FILE_TYPE_IMAGE: "image",
    FILE_TYPE_AUDIO: "audio",
    FILE_TYPE_VIDEO: "video",
    FILE_TYPE_FILE: "file",
    FILE_TYPE_LOCATION: "location",
    FILE_TYPE_FALLBACK: "fallback",
    FILE_TYPE_SHARE: "share",
    FILE_TYPE_STORY_MENTION: "story_mention",
    FILE_TYPE_CONTACT: "contact",
    FILE_TYPE_IG_REEL: "ig_reel",
    FILE_TYPE_IG_POST: "ig_post",
    FILE_TYPE_IG_STORY: "ig_story",
    FILE_TYPE_EMBED: "embed",
}
_FILE_TYPE_STR_TO_INT: dict[str, int] = {v: k for k, v in _FILE_TYPE_INT_TO_STR.items()}


def file_type_to_str(value: int) -> str:
    return _FILE_TYPE_INT_TO_STR.get(value, "image")


def file_type_from_str(value: str) -> int:
    try:
        return _FILE_TYPE_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown file_type: {value!r}") from e


# Sender polymorphic types recognised by Chatwoot.
SENDER_TYPE_USER = "User"
SENDER_TYPE_CONTACT = "Contact"
SENDER_TYPE_AGENT_BOT = "AgentBot"


# =========================================================================
# Conversation
# =========================================================================
class Conversation(TimestampMixin, table=True):
    """Account-scoped conversation between a Contact and one or more Users.

    ``display_id`` is assigned by a Postgres trigger
    (``conv_dpid_seq_<account_id>``) — do NOT write to it from Python.
    See the Alembic migration for the trigger SQL.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        # Hot path: filter by account+inbox+status+assignee.
        Index(
            "conv_acid_inbid_stat_asgnid_idx",
            "account_id",
            "inbox_id",
            "status",
            "assignee_id",
        ),
        Index("index_conversations_on_account_id", "account_id"),
        Index(
            "index_conversations_on_account_id_and_display_id",
            "account_id",
            "display_id",
            unique=True,
        ),
        Index(
            "index_conversations_on_assignee_id_and_account_id",
            "assignee_id",
            "account_id",
        ),
        Index("index_conversations_on_campaign_id", "campaign_id"),
        Index("index_conversations_on_contact_id", "contact_id"),
        Index("index_conversations_on_contact_inbox_id", "contact_inbox_id"),
        Index(
            "index_conversations_on_first_reply_created_at",
            "first_reply_created_at",
        ),
        Index(
            "index_conversations_on_id_and_account_id",
            "account_id",
            "id",
        ),
        Index(
            "index_conversations_on_identifier_and_account_id",
            "identifier",
            "account_id",
        ),
        Index("index_conversations_on_inbox_id", "inbox_id"),
        # Drives the "por anuncio" report breakdown, which groups by ad_id
        # inside an account over a date window.
        Index(
            "index_conversations_on_account_ad_created",
            "account_id",
            "ad_id",
            "created_at",
        ),
        Index("index_conversations_on_priority", "priority"),
        Index(
            "index_conversations_on_status_and_account_id",
            "status",
            "account_id",
        ),
        Index(
            "index_conversations_on_status_and_priority",
            "status",
            "priority",
        ),
        Index("index_conversations_on_team_id", "team_id"),
        Index("index_conversations_on_uuid", "uuid", unique=True),
        Index("index_conversations_on_waiting_since", "waiting_since"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    inbox_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    contact_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    contact_inbox_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("contact_inboxes.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    assignee_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    team_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Schema-parity FK columns without a SA-level ForeignKey. Owning
    # tables land in later phases; adding the FK now would force those
    # tables to migrate into Phase 4a. See module docstring.
    assignee_agent_bot_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    campaign_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    sla_policy_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )

    # DB-trigger-assigned. NEVER set from Python — the trigger overrides
    # whatever Python wrote anyway, but telling SQLAlchemy the column is
    # server-populated stops it from complaining about missing values on
    # INSERT.
    display_id: int = Field(
        default=0,
        sa_column=Column(
            Integer,
            nullable=False,
            server_default=text("0"),
        ),
    )
    uuid: UUID | None = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            nullable=False,
            server_default=text("gen_random_uuid()"),
        ),
    )

    # State
    status: int = Field(
        default=CONVERSATION_STATUS_OPEN,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    priority: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))

    # Lifecycle timestamps
    last_activity_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    agent_last_seen_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    assignee_last_seen_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    contact_last_seen_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    snoozed_until: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    waiting_since: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    first_reply_created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Free-form buckets. Rails' ``before_validation`` coerces nil → {}; we
    # default via ``server_default`` so raw SQL inserts land identically.
    additional_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    custom_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    # Denormalised label cache (``acts_as_taggable_on :labels`` writes to
    # ``tags``/``taggings`` in Rails and caches the CSV here). Labels
    # table lands with Phase 6; the column is nullable text for parity.
    cached_label_list: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    identifier: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # --- Ad attribution (Click-to-WhatsApp / click-to-Messenger) -----------
    # Meta ships a ``referral`` block on the first inbound message when the
    # person arrived from an ad. We denormalise the few fields reports group
    # by into indexed columns, and keep the untouched block in
    # ``ad_referral`` so a payload whose shape we did not anticipate is
    # never lost — the raw copy is what we reconcile against.
    #
    # First touch wins: the ad that *started* the conversation keeps the
    # credit; a later referral on the same thread is logged, not overwritten.
    ad_source: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    ad_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    ad_headline: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    # ``ctwa_clid`` — the click id Meta's Conversions API keys on, kept so
    # conversion reporting back to Meta stays possible later.
    ad_click_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    ad_referral: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    ad_captured_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # v2.8 AI takeover flag. When ``ai_mode`` is true, an external AI
    # agent has claimed this conversation and our own automation rules
    # MUST stand down to avoid fighting it. ``ai_assignee`` is a free-form
    # string the agent stamps on takeover (e.g. ``"alicia-v3"``) so the
    # UI can show which AI is on duty. Both default permissively so
    # existing rows behave exactly as before the migration.
    ai_mode: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    ai_assignee: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )

    # Relationships
    account: "Account" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    inbox: "Inbox" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    contact: "Contact" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    contact_inbox: "ContactInbox" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    assignee: "User" = Relationship(
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "Conversation.assignee_id",
        }
    )
    team: "Team" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    messages: list["Message"] = Relationship(
        back_populates="conversation",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
            "order_by": "Message.created_at",
        },
    )

    @property
    def status_str(self) -> str:
        return conversation_status_to_str(self.status)

    @property
    def priority_str(self) -> str | None:
        return conversation_priority_to_str(self.priority)

    def can_reply(self) -> bool:
        """Placeholder for ``Conversations::MessageWindowService#can_reply?``.

        Full implementation (channel-specific reply windows) lives with
        the email/WA/IG phases. API channel conversations can always
        reply in Phase 4a.
        """
        return True


# =========================================================================
# Message
# =========================================================================
class Message(TimestampMixin, table=True):
    """One chat message inside a ``Conversation``."""

    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "idx_messages_account_content_created",
            "account_id",
            "content_type",
            "created_at",
        ),
        Index(
            "index_messages_on_account_created_type",
            "account_id",
            "created_at",
            "message_type",
        ),
        Index("index_messages_on_account_id", "account_id"),
        Index(
            "index_messages_on_account_id_and_inbox_id",
            "account_id",
            "inbox_id",
        ),
        Index(
            "index_messages_on_conversation_account_type_created",
            "conversation_id",
            "account_id",
            "message_type",
            "created_at",
        ),
        Index("index_messages_on_conversation_id", "conversation_id"),
        Index("index_messages_on_created_at", "created_at"),
        Index("index_messages_on_inbox_id", "inbox_id"),
        Index(
            "index_messages_on_sender_type_and_sender_id",
            "sender_type",
            "sender_id",
        ),
        Index("index_messages_on_source_id", "source_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    inbox_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    conversation_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # Polymorphic sender — parity with Rails ``belongs_to :sender,
    # polymorphic: true``. NO SA-level ForeignKey because the ID points
    # to whichever table ``sender_type`` names.
    sender_type: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    sender_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )

    message_type: int = Field(sa_column=Column(Integer, nullable=False))
    content_type: int = Field(
        default=CONTENT_TYPE_TEXT,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    status: int = Field(
        default=MESSAGE_STATUS_SENT,
        sa_column=Column(Integer, nullable=True, server_default="0"),
    )

    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    processed_message_content: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    # JSON (not JSONB) — matches Rails column type exactly.
    content_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=True, server_default="{}"),
    )
    additional_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, server_default="{}"),
    )
    external_source_ids: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, server_default="{}"),
    )
    sentiment: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, server_default="{}"),
    )

    private: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    source_id: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # Relationships
    account: "Account" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    inbox: "Inbox" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    conversation: "Conversation" = Relationship(
        back_populates="messages", sa_relationship_kwargs={"lazy": "selectin"}
    )
    attachments: list["Attachment"] = Relationship(
        back_populates="message",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )

    @property
    def message_type_str(self) -> str:
        return message_type_to_str(self.message_type)

    @property
    def content_type_str(self) -> str:
        return content_type_to_str(self.content_type)

    @property
    def status_str(self) -> str:
        return message_status_to_str(self.status)

    # Rails has two ``attr_accessor`` transients on Message:
    #   ``echo_id`` — widget optimistic-UI echo (surfaces in push events
    #     and the create response).
    #   ``preserve_waiting_since`` — skip the clear-waiting-since rule
    #     for specific bot/system messages.
    # These are NOT columns. Python-side we pass them as parameters to
    # the service / presenter rather than carrying them on the model, so
    # SQLModel's ORM mapping stays pure. See:
    #   * app.domains.conversations.service.create_message(echo_id=...)
    #   * app.domains.conversations.presenters.present_message(echo_id=...)


# =========================================================================
# Attachment
# =========================================================================
class Attachment(TimestampMixin, table=True):
    """File / image / location / structured payload attached to a message."""

    __tablename__ = "attachments"
    __table_args__ = (
        Index("index_attachments_on_account_id", "account_id"),
        Index("index_attachments_on_message_id", "message_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    message_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    file_type: int = Field(
        default=FILE_TYPE_IMAGE,
        sa_column=Column(Integer, nullable=True, server_default="0"),
    )
    extension: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    external_url: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    fallback_title: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    coordinates_lat: float = Field(
        default=0.0,
        sa_column=Column(Float, nullable=True, server_default="0.0"),
    )
    coordinates_long: float = Field(
        default=0.0,
        sa_column=Column(Float, nullable=True, server_default="0.0"),
    )
    meta: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )

    # Relationships
    message: "Message" = Relationship(
        back_populates="attachments",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    @property
    def file_type_str(self) -> str:
        return file_type_to_str(self.file_type)


# =========================================================================
# Mention
# =========================================================================
class Mention(TimestampMixin, table=True):
    """Pivot: User mentioned in a Conversation (``@agent``)."""

    __tablename__ = "mentions"
    __table_args__ = (
        Index("index_mentions_on_conversation_id", "conversation_id"),
        Index("index_mentions_on_user_id", "user_id"),
        UniqueConstraint(
            "user_id",
            "conversation_id",
            name="index_mentions_on_user_id_and_conversation_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    user_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    conversation_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    mentioned_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


# =========================================================================
# ConversationParticipant
# =========================================================================
class ConversationParticipant(TimestampMixin, table=True):
    """Pivot: agents actively following a conversation (for notifications)."""

    __tablename__ = "conversation_participants"
    __table_args__ = (
        Index(
            "index_conversation_participants_on_conversation_id",
            "conversation_id",
        ),
        Index("index_conversation_participants_on_user_id", "user_id"),
        UniqueConstraint(
            "user_id",
            "conversation_id",
            name="index_conversation_participants_on_user_and_conversation",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    user_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    conversation_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )


# =========================================================================
# ConversationLabel — join row replacing ``acts_as_taggable_on`` taggings
# =========================================================================
class ConversationLabel(TimestampMixin, table=True):
    """One row per (conversation, label) pair.

    Chatwoot uses ``acts_as_taggable_on`` which writes a polymorphic
    ``taggings`` row + a generic ``tags`` row per label. We collapse to
    a direct join because conversations are the only taggable surface in
    the API we ship — no other model uses ``acts_as_taggable_on``.

    The ON DELETE CASCADE on both sides keeps orphan rows from forming
    when a label or conversation is removed (Rails enforces this via
    ``dependent: :destroy`` on the taggings association — we punt to
    the database for the same effect).
    """

    __tablename__ = "conversation_labels"
    __table_args__ = (
        Index("index_conversation_labels_on_conversation_id", "conversation_id"),
        Index("index_conversation_labels_on_label_id", "label_id"),
        UniqueConstraint(
            "conversation_id",
            "label_id",
            name="index_conversation_labels_on_conversation_and_label",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    conversation_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    label_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("labels.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )


__all__ = [
    # enums / constants
    "CONTENT_TYPE_ARTICLE",
    "CONTENT_TYPE_CARDS",
    "CONTENT_TYPE_FORM",
    "CONTENT_TYPE_INCOMING_EMAIL",
    "CONTENT_TYPE_INPUT_CSAT",
    "CONTENT_TYPE_INPUT_EMAIL",
    "CONTENT_TYPE_INPUT_SELECT",
    "CONTENT_TYPE_INPUT_TEXT",
    "CONTENT_TYPE_INPUT_TEXTAREA",
    "CONTENT_TYPE_INTEGRATIONS",
    "CONTENT_TYPE_STICKER",
    "CONTENT_TYPE_TEXT",
    "CONTENT_TYPE_VOICE_CALL",
    "CONVERSATION_PRIORITY_HIGH",
    "CONVERSATION_PRIORITY_LOW",
    "CONVERSATION_PRIORITY_MEDIUM",
    "CONVERSATION_PRIORITY_URGENT",
    "CONVERSATION_STATUS_OPEN",
    "CONVERSATION_STATUS_PENDING",
    "CONVERSATION_STATUS_RESOLVED",
    "CONVERSATION_STATUS_SNOOZED",
    "FILE_TYPE_AUDIO",
    "FILE_TYPE_CONTACT",
    "FILE_TYPE_EMBED",
    "FILE_TYPE_FALLBACK",
    "FILE_TYPE_FILE",
    "FILE_TYPE_IG_POST",
    "FILE_TYPE_IG_REEL",
    "FILE_TYPE_IG_STORY",
    "FILE_TYPE_IMAGE",
    "FILE_TYPE_LOCATION",
    "FILE_TYPE_SHARE",
    "FILE_TYPE_STORY_MENTION",
    "FILE_TYPE_VIDEO",
    "MESSAGE_STATUS_DELIVERED",
    "MESSAGE_STATUS_FAILED",
    "MESSAGE_STATUS_READ",
    "MESSAGE_STATUS_SENT",
    "MESSAGE_TYPE_ACTIVITY",
    "MESSAGE_TYPE_INCOMING",
    "MESSAGE_TYPE_OUTGOING",
    "MESSAGE_TYPE_TEMPLATE",
    "SENDER_TYPE_AGENT_BOT",
    "SENDER_TYPE_CONTACT",
    "SENDER_TYPE_USER",
    # models
    "Attachment",
    "Conversation",
    "ConversationLabel",
    "ConversationParticipant",
    "Mention",
    "Message",
    # converters
    "content_type_from_str",
    "content_type_to_str",
    "conversation_priority_from_str",
    "conversation_priority_to_str",
    "conversation_status_from_str",
    "conversation_status_to_str",
    "file_type_from_str",
    "file_type_to_str",
    "message_status_from_str",
    "message_status_to_str",
    "message_type_from_str",
    "message_type_to_str",
]
