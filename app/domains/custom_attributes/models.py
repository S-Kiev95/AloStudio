"""CustomAttributeDefinition — user-defined attribute schema per account.

Ported from:
  reference/chatwoot/app/models/custom_attribute_definition.rb
  reference/chatwoot/db/schema.rb (v4.13.0)

Parity notes:

* ``attribute_model`` and ``attribute_display_type`` are Rails enum
  columns stored as integers. Chatwoot's ``_custom_attribute_definition.json.jbuilder``
  emits the string form (``'text'``, ``'contact_attribute'``) by
  consuming ``resource.attribute_display_type`` — on a Rails model
  that getter returns the string via the enum mapping. We mirror that
  split: the DB holds integers (schema parity), the presenter emits the
  string (wire parity).

* The unique index ``attribute_key_model_index`` is scoped by
  ``(attribute_key, attribute_model, account_id)`` — so the same
  ``attribute_key`` can coexist across models (one for conversations,
  one for contacts) within the same account.

* ``STANDARD_ATTRIBUTES`` — Chatwoot forbids a ``custom_attribute_key``
  from colliding with a built-in Contact/Conversation field. That guard
  lives in the service layer (``CustomAttributeDefinitionService``) not
  the ORM, because the set is phase-dependent: we only know the
  ``conversation`` side in Phase 4.

Deferred:
  * ``update_widget_pre_chat_custom_fields`` / ``sync_widget_pre_chat_custom_fields``
    callbacks — these enqueue ARQ-equivalent jobs that rewrite the
    ``pre_chat_form_options`` of Channel::WebWidget inboxes. WebWidget
    channel is Phase 5; the hooks are service-layer no-ops for now.
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from app.core.base_model import TimestampMixin

if TYPE_CHECKING:
    from app.domains.accounts.models import Account


# ---- attribute_model enum ----
CUSTOM_ATTR_MODEL_CONVERSATION = 0
CUSTOM_ATTR_MODEL_CONTACT = 1

_ATTR_MODEL_INT_TO_STR: dict[int, str] = {
    CUSTOM_ATTR_MODEL_CONVERSATION: "conversation_attribute",
    CUSTOM_ATTR_MODEL_CONTACT: "contact_attribute",
}
_ATTR_MODEL_STR_TO_INT: dict[str, int] = {v: k for k, v in _ATTR_MODEL_INT_TO_STR.items()}


def attr_model_to_str(value: int) -> str:
    return _ATTR_MODEL_INT_TO_STR.get(value, "conversation_attribute")


def attr_model_from_str(value: str) -> int:
    try:
        return _ATTR_MODEL_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown attribute_model: {value!r}") from e


# ---- attribute_display_type enum ----
CUSTOM_ATTR_TYPE_TEXT = 0
CUSTOM_ATTR_TYPE_NUMBER = 1
CUSTOM_ATTR_TYPE_CURRENCY = 2
CUSTOM_ATTR_TYPE_PERCENT = 3
CUSTOM_ATTR_TYPE_LINK = 4
CUSTOM_ATTR_TYPE_DATE = 5
CUSTOM_ATTR_TYPE_LIST = 6
CUSTOM_ATTR_TYPE_CHECKBOX = 7

_DISPLAY_TYPE_INT_TO_STR: dict[int, str] = {
    CUSTOM_ATTR_TYPE_TEXT: "text",
    CUSTOM_ATTR_TYPE_NUMBER: "number",
    CUSTOM_ATTR_TYPE_CURRENCY: "currency",
    CUSTOM_ATTR_TYPE_PERCENT: "percent",
    CUSTOM_ATTR_TYPE_LINK: "link",
    CUSTOM_ATTR_TYPE_DATE: "date",
    CUSTOM_ATTR_TYPE_LIST: "list",
    CUSTOM_ATTR_TYPE_CHECKBOX: "checkbox",
}
_DISPLAY_TYPE_STR_TO_INT: dict[str, int] = {v: k for k, v in _DISPLAY_TYPE_INT_TO_STR.items()}


def display_type_to_str(value: int) -> str:
    return _DISPLAY_TYPE_INT_TO_STR.get(value, "text")


def display_type_from_str(value: str) -> int:
    try:
        return _DISPLAY_TYPE_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown attribute_display_type: {value!r}") from e


# ---- conflict guard — keys that would shadow a built-in Contact or
#      Conversation field. Mirrors STANDARD_ATTRIBUTES in the Ruby model.
STANDARD_ATTRIBUTE_KEYS: dict[str, frozenset[str]] = {
    "conversation_attribute": frozenset(
        [
            "status",
            "priority",
            "assignee_id",
            "inbox_id",
            "team_id",
            "display_id",
            "campaign_id",
            "labels",
            "browser_language",
            "country_code",
            "referer",
            "created_at",
            "last_activity_at",
        ]
    ),
    "contact_attribute": frozenset(
        [
            "name",
            "email",
            "phone_number",
            "identifier",
            "country_code",
            "city",
            "created_at",
            "last_activity_at",
            "referer",
            "blocked",
        ]
    ),
}


# =========================================================================
# CustomAttributeDefinition
# =========================================================================
class CustomAttributeDefinition(TimestampMixin, table=True):
    __tablename__ = "custom_attribute_definitions"
    __table_args__ = (
        Index("index_custom_attribute_definitions_on_account_id", "account_id"),
        UniqueConstraint(
            "attribute_key",
            "attribute_model",
            "account_id",
            name="attribute_key_model_index",
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
    attribute_display_name: str = Field(sa_column=Column(String, nullable=True))
    attribute_key: str = Field(sa_column=Column(String, nullable=True))
    attribute_description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    attribute_display_type: int = Field(
        default=CUSTOM_ATTR_TYPE_TEXT,
        sa_column=Column(Integer, nullable=True, server_default="0"),
    )
    attribute_model: int = Field(
        default=CUSTOM_ATTR_MODEL_CONVERSATION,
        sa_column=Column(Integer, nullable=True, server_default="0"),
    )
    attribute_values: list[Any] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=True, server_default="[]"),
    )
    default_value: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    regex_pattern: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    regex_cue: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # Relationships
    account: "Account" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    @property
    def attribute_model_str(self) -> str:
        return attr_model_to_str(self.attribute_model)

    @property
    def attribute_display_type_str(self) -> str:
        return display_type_to_str(self.attribute_display_type)


__all__ = [
    "CUSTOM_ATTR_MODEL_CONTACT",
    "CUSTOM_ATTR_MODEL_CONVERSATION",
    "CUSTOM_ATTR_TYPE_CHECKBOX",
    "CUSTOM_ATTR_TYPE_CURRENCY",
    "CUSTOM_ATTR_TYPE_DATE",
    "CUSTOM_ATTR_TYPE_LINK",
    "CUSTOM_ATTR_TYPE_LIST",
    "CUSTOM_ATTR_TYPE_NUMBER",
    "CUSTOM_ATTR_TYPE_PERCENT",
    "CUSTOM_ATTR_TYPE_TEXT",
    "STANDARD_ATTRIBUTE_KEYS",
    "CustomAttributeDefinition",
    "attr_model_from_str",
    "attr_model_to_str",
    "display_type_from_str",
    "display_type_to_str",
]
