"""AutomationRule — event-triggered rule engine.

Ported from:
  reference/chatwoot/app/models/automation_rule.rb
  reference/chatwoot/db/schema.rb (``automation_rules`` table, v4.13.0)

A rule fires when one of the dispatcher's events lands AND its
conditions match the conversation/message in scope. The event the
rule listens for sits in ``event_name``; the conditions and actions
are JSONB arrays validated at the service boundary.

Allowed event names mirror Chatwoot's ``AutomationRuleListener``:
  * conversation_created
  * conversation_updated
  * conversation_opened
  * conversation_resolved
  * message_created

The condition format (one entry):

    {
      "attribute_key": "status",         # what to read off the model
      "filter_operator": "equal_to",     # comparison operator
      "query_operator": "AND",           # joins to the NEXT condition
                                         # ("AND" / "OR" / "" on the last)
      "values": ["open"],                # operator-dependent list
      "custom_attribute_type": null      # "conversation_attribute" /
                                         # "contact_attribute" — optional
    }

The action format mirrors :data:`app.domains.macros.models.MACRO_ALLOWED_ACTIONS`
exactly (the two surfaces share an ``ActionExecutor``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# Event names listed by ``AutomationRuleListener`` — anything else
# is rejected at validation time.
AUTOMATION_RULE_EVENTS: tuple[str, ...] = (
    "conversation_created",
    "conversation_updated",
    "conversation_opened",
    "conversation_resolved",
    "message_created",
)

# Mirrors ``AutomationRule#actions_attributes``. Same superset as Macro
# minus a few extras Macro doesn't expose. Validation re-uses
# ``MACRO_ALLOWED_ACTIONS`` plus these:
AUTOMATION_RULE_EXTRA_ACTIONS: tuple[str, ...] = (
    "send_email_to_team",
    "open_conversation",
    "pending_conversation",
)


def automation_allowed_actions() -> set[str]:
    """Combined allow-list shared with :mod:`app.domains.macros.models`."""
    from app.domains.macros.models import MACRO_ALLOWED_ACTIONS

    return set(MACRO_ALLOWED_ACTIONS) | set(AUTOMATION_RULE_EXTRA_ACTIONS)


# Mirrors ``AutomationRule#conditions_attributes``. Standard keys map
# to columns on Conversation / Contact / Message; custom-attribute keys
# bypass this allow-list via ``custom_attribute_type``.
AUTOMATION_STANDARD_CONDITION_KEYS: tuple[str, ...] = (
    # Conversation columns
    "status",
    "priority",
    "assignee_id",
    "team_id",
    "inbox_id",
    "labels",
    "country_code",
    "city",
    "referer",
    "browser_language",
    "conversation_language",
    # Contact columns
    "email",
    "phone_number",
    "company",
    # Message columns
    "content",
    "message_type",
    "private_note",
    # Email-channel additional
    "mail_subject",
)

AUTOMATION_FILTER_OPERATORS: tuple[str, ...] = (
    "equal_to",
    "not_equal_to",
    "contains",
    "does_not_contain",
    "is_present",
    "is_not_present",
    "is_greater_than",
    "is_less_than",
    "starts_with",
)

AUTOMATION_QUERY_OPERATORS: tuple[str, ...] = ("AND", "OR")


class AutomationRule(TimestampMixin, table=True):
    """Account-scoped rule: when ``event_name`` fires, evaluate
    ``conditions`` against the affected conversation; if they match,
    run ``actions``.
    """

    __tablename__ = "automation_rules"
    __table_args__ = (
        Index("index_automation_rules_on_account_id", "account_id"),
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
    name: str = Field(sa_column=Column(String, nullable=False))
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    event_name: str = Field(sa_column=Column(String, nullable=False))
    active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    conditions: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    actions: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )


__all__ = [
    "AUTOMATION_FILTER_OPERATORS",
    "AUTOMATION_QUERY_OPERATORS",
    "AUTOMATION_RULE_EVENTS",
    "AUTOMATION_RULE_EXTRA_ACTIONS",
    "AUTOMATION_STANDARD_CONDITION_KEYS",
    "AutomationRule",
    "automation_allowed_actions",
]
