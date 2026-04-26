"""Label — account-scoped tag taxonomy for conversations.

Ported from:
  reference/chatwoot/app/models/label.rb
  reference/chatwoot/db/schema.rb (``labels`` table, v4.13.0)

Chatwoot ships ``acts_as_taggable_on :labels`` on Conversation, which
maintains a polymorphic ``taggings`` join table linking conversations
to a generic ``tags`` table — and a separate first-class ``Label`` table
keyed by ``(account_id, title)`` that stores the dashboard-visible
metadata (color, sidebar visibility, description).

We collapse that two-table indirection: ``ConversationLabel`` is a
direct join on ``(conversation_id, label_id)`` that lives on the
:class:`Conversation` side (see ``app.domains.conversations.models``).
The polymorphic ``taggings`` table from acts-as-taggable-on isn't
needed — Chatwoot's only taggable type is ``Conversation`` in the API
surface we ship.

The denormalised ``conversations.cached_label_list`` CSV is still
populated on writes so that the index/search path can filter by label
without joining (matches Chatwoot's read-side behaviour).
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# We deliberately omit a ``account: "Account"`` Relationship on Label —
# nothing in the activity / labels code path navigates Label -> Account,
# the FK is enough. Skipping the relationship sidesteps the SQLAlchemy
# mapper-configuration order pitfall (Label's mapper can be touched
# before ``app.domains.accounts.models`` has been imported, since this
# module is loaded lazily inside service functions).


# Rails default ``color: "#1f93ff"`` — re-stated here so a fresh insert
# omitting the column lands the same hex Chatwoot ships.
DEFAULT_LABEL_COLOR = "#1f93ff"


class Label(TimestampMixin, table=True):
    """A user-named tag, scoped to a single account.

    Chatwoot's ``before_validation`` lowercases ``title`` so "Urgent"
    and "urgent" collapse — we do the same in the service layer.

    The ``acts_as_taggable_on`` cache invalidator
    (``after_update_commit :update_associated_models``) is a Rails-side
    rename helper that walks all conversations using the old title and
    rewrites their ``cached_label_list``. We don't need it here:
    ``ConversationLabel`` references ``label_id``, so the join survives
    a rename — but we DO refresh the CSV when titles change (see
    ``app.domains.labels.service.rename_label`` if/when ported).
    """

    __tablename__ = "labels"
    __table_args__ = (
        Index("index_labels_on_account_id", "account_id"),
        UniqueConstraint(
            "title", "account_id", name="index_labels_on_title_and_account_id"
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    title: str = Field(sa_column=Column(String, nullable=False))
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    color: str = Field(
        default=DEFAULT_LABEL_COLOR,
        sa_column=Column(String, nullable=False, server_default=DEFAULT_LABEL_COLOR),
    )
    show_on_sidebar: bool | None = Field(
        default=None, sa_column=Column(Boolean, nullable=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )


__all__ = ["DEFAULT_LABEL_COLOR", "Label"]
