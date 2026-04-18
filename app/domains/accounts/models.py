"""Account — the top-level tenant.

Ported from reference/chatwoot/app/models/account.rb + db/schema.rb (v4.13.0).

Phase 1 keeps the full column set because Chatwoot serialises most of these in
`/api/v1/accounts/:id` responses, and we want byte-identical parity. Columns
that only matter later in the roadmap (feature_flags, limits, internal_attributes,
auto_resolve_duration, domain, support_email) are present but not wired into
services yet.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, BigInteger, Column, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from app.core.base_model import TimestampMixin

if TYPE_CHECKING:
    from app.domains.users.models import AccountUser


# ----------------------------------------------------------------------
# Enums — integer-backed to match Rails schema (not PG enum types)
#
# Chatwoot's `status` is `active=0, suspended=1`; `locale` is a wide mapping of
# ISO codes to integer indices defined in LANGUAGES_CONFIG. We store the integer
# and translate to/from the code at the service boundary (see schemas.py).
# ----------------------------------------------------------------------

ACCOUNT_STATUS_ACTIVE = 0
ACCOUNT_STATUS_SUSPENDED = 1

# Minimal locale mapping. Extend as we import more LANGUAGES_CONFIG entries.
# Chatwoot's canonical list:
#   reference/chatwoot/config/locales.rb (LANGUAGES_CONFIG)
ACCOUNT_LOCALE_CODE_TO_INT: dict[str, int] = {"en": 0}
ACCOUNT_LOCALE_INT_TO_CODE: dict[int, str] = {v: k for k, v in ACCOUNT_LOCALE_CODE_TO_INT.items()}


class Account(TimestampMixin, table=True):
    __tablename__ = "accounts"

    # `id: :serial` in Rails schema → Postgres INTEGER
    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    locale: int = Field(
        default=0, sa_column=Column(Integer, nullable=True, server_default="0")
    )
    domain: str | None = Field(
        default=None, sa_column=Column(String(100), nullable=True)
    )
    support_email: str | None = Field(
        default=None, sa_column=Column(String(100), nullable=True)
    )
    feature_flags: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, server_default="0")
    )
    auto_resolve_duration: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    limits: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=True, server_default="{}")
    )
    custom_attributes: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=True, server_default="{}")
    )
    status: int = Field(
        default=ACCOUNT_STATUS_ACTIVE,
        sa_column=Column(Integer, nullable=True, server_default="0", index=True),
    )
    internal_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    settings: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=True, server_default="{}")
    )

    # Relationships
    account_users: list["AccountUser"] = Relationship(
        back_populates="account",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )

    # Convenience — not persisted
    @property
    def locale_code(self) -> str:
        return ACCOUNT_LOCALE_INT_TO_CODE.get(self.locale, "en")
