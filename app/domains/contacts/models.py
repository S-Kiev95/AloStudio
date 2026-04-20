"""Contact + ContactInbox + Note.

Ported from:
  reference/chatwoot/app/models/contact.rb
  reference/chatwoot/app/models/contact_inbox.rb
  reference/chatwoot/app/models/note.rb
  reference/chatwoot/db/schema.rb (v4.13.0)

Column-level parity notes:

* ``contacts.email`` carries a **case-insensitive** unique index
  (``index_contacts_on_lower_email_account_id`` on
  ``lower(email), account_id``). We replicate that with a functional
  ``Index`` below. The ``before_validation`` lowercasing from Rails
  lives in :mod:`app.domains.contacts.service` so the write path is
  explicit rather than hidden behind an ORM hook.

* ``contacts.contact_type`` is an integer-backed Rails enum
  (``visitor: 0, lead: 1, customer: 2``). Stored as Integer for
  schema parity; the string form is derived in the presenter when
  needed. Phase 3 doesn't surface ``contact_type`` on any endpoint
  — the jbuilder doesn't emit it — but the column is kept so the
  schema matches byte-for-byte against a v4.13.0 dump.

* ``additional_attributes`` + ``custom_attributes`` are nullable JSONB
  in Chatwoot's schema but Rails' ``before_validation`` coerces them
  to ``{}``. We set ``server_default='{}'`` + ``nullable=False`` on
  the ORM side — *widening* of the schema that doesn't break parity
  on the wire (callers never see NULL).

* ``contact_inboxes.hmac_verified`` default false; ``pubsub_token`` is a
  Base58(24) token generated at create time (mirrors the
  ``Pubsubable`` concern's ``has_secure_token :pubsub_token``).

* ``notes.account_id`` is backfilled from ``contact.account_id`` in a
  ``before_validation`` hook on Chatwoot's side. We do the same in the
  service layer (see :mod:`app.domains.contacts.service`).

Deferred (Phase-later):
  * ``has_many :conversations`` / ``has_many :messages, as: :sender``
    — those tables land in Phase 4; the Contact relationships are
    NOT declared here to avoid importing Phase 4 models prematurely.
    ``ContactMergeAction`` already flags this explicitly.
  * ``Avatarable`` / ``AvailabilityStatusable`` concerns — avatar
    attachment + Redis presence. The presenter returns a static
    ``"offline"`` + empty-string thumbnail until those land.
  * ``acts_as_taggable_on :labels`` — Phase 4 bundles labels with
    Conversations.
  * ``company_id`` FK — there is no companies table in Phase 3; we keep
    the column to match schema.rb but no ForeignKey is declared.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from app.core.base_model import TimestampMixin
from app.core.tokens import base58_token

if TYPE_CHECKING:
    from app.domains.accounts.models import Account
    from app.domains.inboxes.models import Inbox
    from app.domains.users.models import User


# ``contact_type`` enum — stored as int in Chatwoot.
CONTACT_TYPE_VISITOR = 0
CONTACT_TYPE_LEAD = 1
CONTACT_TYPE_CUSTOMER = 2

_CONTACT_TYPE_INT_TO_STR: dict[int, str] = {
    CONTACT_TYPE_VISITOR: "visitor",
    CONTACT_TYPE_LEAD: "lead",
    CONTACT_TYPE_CUSTOMER: "customer",
}


def contact_type_to_str(value: int) -> str:
    return _CONTACT_TYPE_INT_TO_STR.get(value, "visitor")


# =========================================================================
# Contact
# =========================================================================
class Contact(TimestampMixin, table=True):
    """Account-scoped contact (customer/lead/visitor)."""

    __tablename__ = "contacts"
    __table_args__ = (
        Index("index_contacts_on_account_id", "account_id"),
        Index(
            "index_contacts_on_account_id_and_contact_type",
            "account_id",
            "contact_type",
        ),
        Index(
            "index_contacts_on_account_id_and_last_activity_at",
            "account_id",
            "last_activity_at",
        ),
        Index("index_contacts_on_blocked", "blocked"),
        Index("index_contacts_on_company_id", "company_id"),
        # Case-insensitive email index — matches Rails'
        # ``index_contacts_on_lower_email_account_id (lower(email),
        # account_id)`` functional index.
        Index(
            "index_contacts_on_lower_email_account_id",
            func.lower(Column("email")),
            "account_id",
        ),
        Index(
            "index_contacts_on_phone_number_and_account_id",
            "phone_number",
            "account_id",
        ),
        UniqueConstraint(
            "email", "account_id", name="uniq_email_per_account_contact"
        ),
        UniqueConstraint(
            "identifier", "account_id", name="uniq_identifier_per_account_contact"
        ),
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

    # ------- identity fields --------
    name: str = Field(default="", sa_column=Column(String, nullable=True, server_default=""))
    email: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    phone_number: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    identifier: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # ------- profile --------
    middle_name: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    last_name: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    location: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    country_code: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )

    # ------- flags + timestamps --------
    blocked: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    contact_type: int = Field(
        default=CONTACT_TYPE_VISITOR,
        sa_column=Column(Integer, nullable=True, server_default="0"),
    )
    last_activity_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # ------- JSONB blobs --------
    additional_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    custom_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    # ------- company FK column kept for schema parity, no FK declared --------
    company_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))

    # Relationships
    account: "Account" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    contact_inboxes: list["ContactInbox"] = Relationship(
        back_populates="contact",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )
    notes: list["Note"] = Relationship(
        back_populates="contact",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )

    @property
    def contact_type_str(self) -> str:
        return contact_type_to_str(self.contact_type)


# =========================================================================
# ContactInbox
# =========================================================================
class ContactInbox(TimestampMixin, table=True):
    """Join row between Contact and Inbox, carrying the per-channel session key.

    ``source_id`` is Chatwoot's per-channel identity:
      * API / WebWidget → random UUID
      * Email           → contact.email
      * SMS / WhatsApp  → contact.phone_number (WA strips ``+``)
      * Twilio SMS/WA   → ``phone_number`` or ``whatsapp:<phone_number>``

    Phase 3 only implements the API-channel branch. Other branches raise
    ``NotImplementedError`` in :class:`app.domains.contacts.service.ContactInboxBuilder`.

    The UNIQUE index on ``(inbox_id, source_id)`` matches Chatwoot's
    ``index_contact_inboxes_on_inbox_id_and_source_id UNIQUE``. The
    UNIQUE index on ``pubsub_token`` mirrors the ``Pubsubable`` concern.
    """

    __tablename__ = "contact_inboxes"
    __table_args__ = (
        Index("index_contact_inboxes_on_contact_id", "contact_id"),
        Index("index_contact_inboxes_on_inbox_id", "inbox_id"),
        Index("index_contact_inboxes_on_source_id", "source_id"),
        # Named unique indexes (not ``UNIQUE`` constraints) to match Chatwoot's
        # ``index_contact_inboxes_on_inbox_id_and_source_id`` and
        # ``index_contact_inboxes_on_pubsub_token`` in schema.rb.
        Index(
            "index_contact_inboxes_on_inbox_id_and_source_id",
            "inbox_id",
            "source_id",
            unique=True,
        ),
        Index("index_contact_inboxes_on_pubsub_token", "pubsub_token", unique=True),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    contact_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    inbox_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    source_id: str = Field(sa_column=Column(Text, nullable=False))
    pubsub_token: str | None = Field(
        default_factory=lambda: base58_token(24),
        sa_column=Column(String, nullable=True),
    )
    hmac_verified: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )

    # Relationships
    contact: "Contact" = Relationship(
        back_populates="contact_inboxes",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    inbox: "Inbox" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


# =========================================================================
# Note
# =========================================================================
class Note(TimestampMixin, table=True):
    """Agent-visible note attached to a contact."""

    __tablename__ = "notes"
    __table_args__ = (
        Index("index_notes_on_account_id", "account_id"),
        Index("index_notes_on_contact_id", "contact_id"),
        Index("index_notes_on_user_id", "user_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
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
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Relationships
    contact: "Contact" = Relationship(
        back_populates="notes",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    user: "User" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


__all__ = [
    "CONTACT_TYPE_CUSTOMER",
    "CONTACT_TYPE_LEAD",
    "CONTACT_TYPE_VISITOR",
    "Contact",
    "ContactInbox",
    "Note",
    "contact_type_to_str",
]
