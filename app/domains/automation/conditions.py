"""Condition evaluator for AutomationRule.

Ported from:
  reference/chatwoot/app/services/automation_rules/conditions_filter_service.rb
  reference/chatwoot/lib/filters/filter_keys.yml (attribute → table mapping)

Strategy: Chatwoot's evaluator builds a raw SQL WHERE clause and
counts matching rows on a JOIN of conversations + contacts +
messages. We sidestep that and evaluate each condition in Python
against the in-memory objects already in scope (Conversation,
Contact, Message). Same observable semantics, no SQL string
concatenation, no extra round-trip.

The condition dict shape (one entry):

    {
      "attribute_key":          str,
      "filter_operator":        str,        # equal_to / contains / ...
      "query_operator":         "AND"|"OR"|"" ,  # joins to NEXT
      "values":                 [Any, ...],
      "custom_attribute_type":  str | None  # "conversation_attribute" /
                                            # "contact_attribute"
    }

Combination semantics: ``query_operator`` on entry N joins entry N's
result with entry N+1's result, evaluated left-to-right. The last
condition's ``query_operator`` is empty / null. Mirrors Rails'
WHERE clause concatenation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domains.contacts.models import Contact
from app.domains.conversations.models import (
    Conversation,
    Message,
    conversation_priority_to_str,
    conversation_status_to_str,
    message_type_to_str,
)
from app.domains.inboxes.models import Inbox

log = logging.getLogger(__name__)


# Attribute keys whose value lives on Contact rather than Conversation.
_CONTACT_KEYS = {"email", "phone_number", "company"}

# Attribute keys whose value lives on Message rather than Conversation.
_MESSAGE_KEYS = {"content", "message_type", "private_note"}

# Conversation columns whose stored int needs decoding to a string before
# comparison. Chatwoot stores the enum as int but compares against the
# string label (e.g. ``status == "open"``).
_CONVERSATION_INT_ENUMS = {
    "status": conversation_status_to_str,
    "priority": conversation_priority_to_str,
}


# ---------------------------------------------------------------------------
# Attribute resolution
# ---------------------------------------------------------------------------
def _resolve_attribute(
    attribute_key: str,
    *,
    conversation: Conversation,
    message: Message | None,
    contact: Contact | None,
) -> Any:
    """Pull the value for ``attribute_key`` off the right model.

    Returns ``None`` when the attribute isn't reachable (e.g. a
    contact-side condition with no contact loaded). The caller's
    ``is_present`` / ``is_not_present`` operators interpret ``None``
    correctly without special-casing.
    """
    if attribute_key == "labels":
        # Chatwoot keeps labels on the conversation via
        # ``acts_as_taggable_on``. We use the denormalised
        # ``cached_label_list`` CSV — read it as a list of strings.
        csv = conversation.cached_label_list or ""
        return [t.strip() for t in csv.split(",") if t.strip()]

    if attribute_key in _CONVERSATION_INT_ENUMS:
        decode = _CONVERSATION_INT_ENUMS[attribute_key]
        raw = getattr(conversation, attribute_key, None)
        return decode(raw) if raw is not None else None

    if attribute_key in {"assignee_id", "team_id", "inbox_id"}:
        return getattr(conversation, attribute_key, None)

    if attribute_key in {"country_code", "city", "referer", "browser_language"}:
        # Chatwoot stores these on
        # ``conversation.additional_attributes['browser']`` / similar
        # nested keys. The stand-alone form lives at top-level too —
        # check both.
        attrs = conversation.additional_attributes or {}
        if attribute_key in attrs:
            return attrs.get(attribute_key)
        browser = attrs.get("browser") or {}
        return browser.get(attribute_key)

    if attribute_key == "conversation_language":
        return (
            (conversation.additional_attributes or {}).get(
                "conversation_language"
            )
        )

    if attribute_key == "mail_subject":
        # Email channel stamps the subject onto the first message's
        # content_attributes. Read off the message we have in scope.
        if message is None:
            return None
        ca = message.content_attributes or {}
        return ca.get("email", {}).get("subject") or ca.get("subject")

    if attribute_key in _CONTACT_KEYS:
        if contact is None:
            return None
        return getattr(contact, attribute_key, None)

    if attribute_key in _MESSAGE_KEYS:
        if message is None:
            return None
        if attribute_key == "content":
            # Mirror Rails' ``attribute_key = 'processed_message_content'
            # if attribute_key == 'content'`` rewrite.
            return message.processed_message_content or message.content
        if attribute_key == "message_type":
            return message_type_to_str(message.message_type)
        if attribute_key == "private_note":
            return message.private
        return getattr(message, attribute_key, None)

    return None


def _resolve_custom_attribute(
    attribute_key: str,
    custom_attribute_type: str | None,
    *,
    conversation: Conversation,
    contact: Contact | None,
) -> Any:
    """Look up a custom-attribute value on the right JSONB column."""
    if custom_attribute_type == "conversation_attribute":
        return (conversation.custom_attributes or {}).get(attribute_key)
    if custom_attribute_type == "contact_attribute":
        if contact is None:
            return None
        return (contact.custom_attributes or {}).get(attribute_key)
    return None


# ---------------------------------------------------------------------------
# Operator dispatch
# ---------------------------------------------------------------------------
def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _coerce_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _matches_equal(actual: Any, values: list[Any]) -> bool:
    if isinstance(actual, list):
        # Multi-valued attribute (e.g. labels) — Chatwoot's tag join
        # matches when ANY label name equals ANY listed value.
        actual_strs = {_coerce_str(v) for v in actual}
        wanted_strs = {_coerce_str(v) for v in values}
        return bool(actual_strs & wanted_strs)
    actual_str = _coerce_str(actual)
    return actual_str in {_coerce_str(v) for v in values}


def _matches_contains(actual: Any, values: list[Any]) -> bool:
    if actual is None:
        return False
    if isinstance(actual, list):
        # Labels-on-conversation: contains the listed value
        actual_strs = [_coerce_str(v) for v in actual]
        for v in values:
            needle = _coerce_str(v)
            if needle is None:
                continue
            if any(needle in (a or "") for a in actual_strs):
                return True
        return False
    actual_str = _coerce_str(actual) or ""
    haystack = actual_str.lower()
    return any(
        (_coerce_str(v) or "").lower() in haystack for v in values
    )


def _matches_starts_with(actual: Any, values: list[Any]) -> bool:
    if actual is None:
        return False
    actual_str = (_coerce_str(actual) or "").lower()
    return any(
        actual_str.startswith((_coerce_str(v) or "").lower())
        for v in values
    )


def _matches_present(actual: Any) -> bool:
    """Mirror Rails' ``IS NOT NULL`` / ``present?`` semantics."""
    if actual is None:
        return False
    if isinstance(actual, str):
        return bool(actual.strip())
    if isinstance(actual, list | tuple | set | dict):
        return len(actual) > 0
    return True


def _matches_compare(actual: Any, values: list[Any], op: str) -> bool:
    if not values:
        return False
    a = _coerce_number(actual)
    b = _coerce_number(values[0])
    if a is None or b is None:
        return False
    if op == "is_greater_than":
        return a > b
    if op == "is_less_than":
        return a < b
    return False


def _evaluate_one(
    condition: dict[str, Any],
    *,
    conversation: Conversation,
    message: Message | None,
    contact: Contact | None,
) -> bool:
    attribute_key = condition.get("attribute_key")
    filter_operator = condition.get("filter_operator")
    values = condition.get("values") or []
    custom_attribute_type = condition.get("custom_attribute_type")

    if not isinstance(attribute_key, str) or not isinstance(filter_operator, str):
        return False

    if custom_attribute_type:
        actual = _resolve_custom_attribute(
            attribute_key,
            custom_attribute_type,
            conversation=conversation,
            contact=contact,
        )
    else:
        actual = _resolve_attribute(
            attribute_key,
            conversation=conversation,
            message=message,
            contact=contact,
        )

    op = filter_operator
    if op == "equal_to":
        return _matches_equal(actual, values)
    if op == "not_equal_to":
        return not _matches_equal(actual, values)
    if op == "contains":
        return _matches_contains(actual, values)
    if op == "does_not_contain":
        return not _matches_contains(actual, values)
    if op == "starts_with":
        return _matches_starts_with(actual, values)
    if op == "is_present":
        return _matches_present(actual)
    if op == "is_not_present":
        return not _matches_present(actual)
    if op in {"is_greater_than", "is_less_than"}:
        return _matches_compare(actual, values, op)
    log.warning(
        "automation.condition.unknown_operator op=%s attribute_key=%s",
        op,
        attribute_key,
    )
    return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def evaluate_conditions(
    conditions: list[dict[str, Any]] | None,
    *,
    conversation: Conversation,
    message: Message | None = None,
    contact: Contact | None = None,
) -> bool:
    """Evaluate the rule's conditions list against in-scope objects.

    Empty / missing conditions evaluate to True (mirrors Rails: an
    empty WHERE clause matches every row). Per-condition errors fall
    through to False — never raise.
    """
    if not conditions:
        return True
    try:
        # First condition seeds the running result.
        first = conditions[0]
        result = _evaluate_one(
            first,
            conversation=conversation,
            message=message,
            contact=contact,
        )
        for i in range(1, len(conditions)):
            join_op = (conditions[i - 1].get("query_operator") or "AND").upper()
            this = _evaluate_one(
                conditions[i],
                conversation=conversation,
                message=message,
                contact=contact,
            )
            if join_op == "OR":
                result = result or this
            else:
                result = result and this
        return bool(result)
    except Exception:  # noqa: BLE001
        log.exception(
            "automation.condition.evaluator_error conversation_id=%s",
            conversation.id,
        )
        return False


# Keep mapper-config quiet — these models are already loaded by the
# domain modules that import this file, but reach-in via attribute
# names benefits from an explicit reference.
_ = (Inbox,)


__all__ = ["evaluate_conditions"]
