"""CustomView — a saved conversation/contact filter, private to one user.

Ported from:
  reference/chatwoot/app/models/custom_view.rb
  reference/chatwoot/app/controllers/api/v1/accounts/custom_filters_controller.rb

Chatwoot names the model ``CustomView`` but routes it under
``custom_filters`` (``CustomFiltersController``). A row stores a named
filter-DSL ``query`` (``{"payload": [<condition>, ...]}``) the user can
re-apply from the conversation (or contact) list. ``filter_type`` is an
int enum (conversation=0, contact=1); each row belongs to both an account
and the user who saved it, so views stay private to their author.

No SQLAlchemy ``Relationship`` is declared (only the FK columns) — nothing
in this slice navigates CustomView -> Account/User, and skipping the
relationships sidesteps the mapper-config order pitfall the Label model
documents.
"""

from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# ---------------------------------------------------------------------------
# CustomView.filter_type enum (mirrors Rails ``enum filter_type``)
# ---------------------------------------------------------------------------
CUSTOM_VIEW_TYPE_CONVERSATION = 0
CUSTOM_VIEW_TYPE_CONTACT = 1

_TYPE_INT_TO_STR: dict[int, str] = {
    CUSTOM_VIEW_TYPE_CONVERSATION: "conversation",
    CUSTOM_VIEW_TYPE_CONTACT: "contact",
}
_TYPE_STR_TO_INT: dict[str, int] = {v: k for k, v in _TYPE_INT_TO_STR.items()}


def custom_view_type_to_str(value: int) -> str:
    return _TYPE_INT_TO_STR.get(value, "conversation")


def custom_view_type_from_str(value: str | None) -> int:
    if value is None or value == "":
        return CUSTOM_VIEW_TYPE_CONVERSATION
    return _TYPE_STR_TO_INT.get(value, CUSTOM_VIEW_TYPE_CONVERSATION)


class CustomView(TimestampMixin, table=True):
    """A user-named, account-scoped saved filter."""

    __tablename__ = "custom_views"
    __table_args__ = (
        Index("index_custom_views_on_account_id", "account_id"),
        Index("index_custom_views_on_user_id", "user_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    filter_type: int = Field(
        default=CUSTOM_VIEW_TYPE_CONVERSATION,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    query: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
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


__all__ = [
    "CUSTOM_VIEW_TYPE_CONTACT",
    "CUSTOM_VIEW_TYPE_CONVERSATION",
    "CustomView",
    "custom_view_type_from_str",
    "custom_view_type_to_str",
]
