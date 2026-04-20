"""Inbox + ApiChannel + InboxMember.

Ported from:
  reference/chatwoot/app/models/inbox.rb
  reference/chatwoot/app/models/channel/api.rb
  reference/chatwoot/app/models/inbox_member.rb
  reference/chatwoot/db/schema.rb (v4.13.0)

Phase 2 scope: only the ``Channel::Api`` concrete channel is wired up. Other
channel classes (``Channel::Email``, ``Channel::FacebookPage``, etc.) will
live in sibling modules under ``app/domains/inboxes/channels/`` when their
phase arrives. The ``Inbox.channel_type`` / ``Inbox.channel_id`` columns are
*polymorphic without a foreign key* — exactly how Chatwoot stores it — so
adding more channel models later is additive.

Notable omissions (deferred):
  * ``portal_id`` column is kept (schema parity with v4.13.0) but the FK
    to ``portals`` is not declared because Portal is Phase 6+.
  * Round-robin hooks on ``InboxMember`` — Chatwoot kicks
    ``AutoAssignment::InboxRoundRobinService`` from ``after_create`` /
    ``after_destroy`` callbacks. We don't run auto-assignment yet, so the
    hooks are service-layer no-ops until Phase 5 (conversations + routing).
  * ``working_hours`` has its own table (``working_hours``) joined by
    inbox_id — that table lives in its own phase; the inbox response
    presenter surfaces an empty schedule for now.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from app.core.base_model import TimestampMixin
from app.core.tokens import base58_token

if TYPE_CHECKING:
    from app.domains.accounts.models import Account
    from app.domains.users.models import User


# ------------------------------------------------------------------ constants
# ``sender_name_type`` enum from Chatwoot (``enum sender_name_type: {...}``).
# Stored as integer in the DB; we expose the string at the wire boundary.
INBOX_SENDER_NAME_FRIENDLY = 0
INBOX_SENDER_NAME_PROFESSIONAL = 1
_SENDER_NAME_INT_TO_STR: dict[int, str] = {
    INBOX_SENDER_NAME_FRIENDLY: "friendly",
    INBOX_SENDER_NAME_PROFESSIONAL: "professional",
}
_SENDER_NAME_STR_TO_INT: dict[str, int] = {v: k for k, v in _SENDER_NAME_INT_TO_STR.items()}


# ``channel_type`` stores the Ruby class name verbatim (``'Channel::Api'``,
# ``'Channel::Email'``, …). We keep the Ruby spelling so a side-by-side DB
# dump against Chatwoot lines up identically.
CHANNEL_TYPE_API = "Channel::Api"


def sender_name_type_to_str(value: int) -> str:
    return _SENDER_NAME_INT_TO_STR.get(value, "friendly")


def sender_name_type_from_str(value: str) -> int:
    try:
        return _SENDER_NAME_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown sender_name_type: {value!r}") from e


# =========================================================================
# ApiChannel (Channel::Api)
# =========================================================================
class ApiChannel(TimestampMixin, table=True):
    """Concrete channel for ``Channel::Api`` — the generic HTTP API channel.

    Chatwoot stores channel rows in per-type tables (``channel_api``,
    ``channel_email``, …) — no shared channels table. The Inbox joins via
    polymorphic ``(channel_type, channel_id)`` columns without a real FK,
    so each channel table is a standalone island.

    ``identifier``, ``hmac_token``, and ``secret`` come from Rails'
    ``has_secure_token`` + ``WebhookSecretable`` concerns — 24-char Base58
    tokens generated at create time. ``identifier`` and ``hmac_token`` carry
    UNIQUE indexes so a collision would surface as an IntegrityError rather
    than silent overwrites.
    """

    __tablename__ = "channel_api"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    webhook_url: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # has_secure_token :identifier / :hmac_token + WebhookSecretable :secret
    identifier: str | None = Field(
        default_factory=lambda: base58_token(24),
        sa_column=Column(String, nullable=True, unique=True),
    )
    hmac_token: str | None = Field(
        default_factory=lambda: base58_token(24),
        sa_column=Column(String, nullable=True, unique=True),
    )
    secret: str | None = Field(
        default_factory=lambda: base58_token(24),
        sa_column=Column(String, nullable=True),
    )

    hmac_mandatory: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    additional_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, server_default="{}"),
    )


# =========================================================================
# Inbox
# =========================================================================
class Inbox(TimestampMixin, table=True):
    """Generic channel wrapper — one row per agent-facing inbox.

    The ``channel_type`` / ``channel_id`` pair is a Rails polymorphic
    association with *no FK* — Postgres doesn't know about the link, so
    deletes cascade via the Ruby ``dependent: :destroy_async`` hook, which
    we replicate in the service layer (see :mod:`app.domains.inboxes.service`).
    """

    __tablename__ = "inboxes"
    __table_args__ = (
        Index("index_inboxes_on_account_id", "account_id"),
        Index(
            "index_inboxes_on_channel_id_and_channel_type",
            "channel_id",
            "channel_type",
        ),
        Index("index_inboxes_on_portal_id", "portal_id"),
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
    channel_id: int = Field(sa_column=Column(Integer, nullable=False))
    channel_type: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    name: str = Field(sa_column=Column(String, nullable=False))
    business_name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    email_address: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # Feature toggles — all default TRUE/FALSE per Chatwoot schema
    enable_auto_assignment: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=True, server_default="true"),
    )
    enable_email_collect: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=True, server_default="true"),
    )
    greeting_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    greeting_message: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    working_hours_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    out_of_office_message: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    timezone: str = Field(
        default="UTC",
        sa_column=Column(String, nullable=True, server_default="UTC"),
    )
    csat_survey_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    allow_messages_after_resolved: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=True, server_default="true"),
    )
    lock_to_single_conversation: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )

    # ``sender_name_type`` — 0=friendly, 1=professional (integer enum in Rails)
    sender_name_type: int = Field(
        default=INBOX_SENDER_NAME_FRIENDLY,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )

    # JSONB blobs — shape owned by the service layer, schema stays permissive
    auto_assignment_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, server_default="{}"),
    )
    csat_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    # Portal FK is deferred until Phase 6 (HelpCenter) — keep column for
    # schema parity, no SA-level ForeignKey declared yet.
    portal_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))

    # Relationships
    account: "Account" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    inbox_members: list["InboxMember"] = Relationship(
        back_populates="inbox",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )

    # ---- helpers (not persisted) -------------------------------------
    @property
    def sender_name_type_str(self) -> str:
        return sender_name_type_to_str(self.sender_name_type)

    def is_api(self) -> bool:
        return self.channel_type == CHANNEL_TYPE_API


# =========================================================================
# InboxMember
# =========================================================================
class InboxMember(TimestampMixin, table=True):
    """Agent ↔ Inbox join row.

    Chatwoot attaches two callbacks here:
      * ``after_create`` → ``InboxRoundRobinService#add_agent_to_queue``
      * ``after_destroy`` → ``InboxRoundRobinService#remove_agent_from_queue``

    Auto-assignment isn't wired yet (Phase 5), so we don't replicate those
    callbacks at the ORM level. The service-layer helpers in
    :mod:`app.domains.inboxes.service` will be the future injection point
    when round-robin arrives.
    """

    __tablename__ = "inbox_members"
    __table_args__ = (
        UniqueConstraint(
            "inbox_id", "user_id", name="index_inbox_members_on_inbox_id_and_user_id"
        ),
        Index("index_inbox_members_on_inbox_id", "inbox_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("users.id", ondelete="CASCADE"),
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

    # Chatwoot uses ``precision: nil`` on these two columns (timestamp
    # without fractional seconds). We inherit the base ``TimestampMixin``
    # columns instead of overriding — ``DateTime(timezone=True)`` with
    # default precision is a harmless precision-widening, not a schema
    # break. Flagged here so nobody writes a parity assertion against
    # microsecond-level equality.

    # Relationships
    inbox: "Inbox" = Relationship(
        back_populates="inbox_members",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    user: "User" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


__all__ = [
    "CHANNEL_TYPE_API",
    "INBOX_SENDER_NAME_FRIENDLY",
    "INBOX_SENDER_NAME_PROFESSIONAL",
    "ApiChannel",
    "Inbox",
    "InboxMember",
    "sender_name_type_from_str",
    "sender_name_type_to_str",
]
