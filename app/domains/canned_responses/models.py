"""CannedResponse — reusable ``/short_code`` reply snippets, per account.

Ported from:
  reference/chatwoot/app/models/canned_response.rb
  reference/chatwoot/db/schema.rb (``canned_responses`` table, v4.13.0)

An agent types ``/<short_code>`` in the composer and the matching
``content`` is inserted. Each response is scoped to one account and the
``short_code`` is unique within that account (Rails
``validates :short_code, uniqueness: { scope: :account_id }``) — an
app-level check we mirror in the service, since Chatwoot's schema ships
no backing DB index.

Chatwoot's original table is ``id: :serial`` with no indexes beyond the
PK. We standardise on ``BigInteger`` PKs (as every other AloStudio table
does) and add ``index_canned_responses_on_account_id`` since every query
is account-scoped — a supporting-index divergence from the reference
schema, nothing behavioural.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin


class CannedResponse(TimestampMixin, table=True):
    """A ``/short_code`` → ``content`` snippet owned by one Account.

    ``short_code`` / ``content`` are nullable at the DB level (matching
    ``schema.rb``); presence is enforced in the service layer, mirroring
    the ActiveRecord validations.
    """

    __tablename__ = "canned_responses"
    __table_args__ = (
        Index("index_canned_responses_on_account_id", "account_id"),
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
    short_code: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    content: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )


__all__ = ["CannedResponse"]
