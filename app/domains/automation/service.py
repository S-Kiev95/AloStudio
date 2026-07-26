"""AutomationRule CRUD service + run-on-conversation glue.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/automation_rules_controller.rb
  reference/chatwoot/app/models/automation_rule.rb (validations)
  reference/chatwoot/app/services/automation_rules/condition_validation_service.rb
  reference/chatwoot/app/services/automation_rules/action_service.rb
  reference/chatwoot/app/listeners/automation_rule_listener.rb (run/skip flow)

This module owns:

  * Validation of the conditions / actions / event_name / query_operator
    payload on create + update (Rails ``json_*_format`` + ``query_operator_*``).
  * The CRUD operations + clone shorthand.
  * :func:`run_rule_on_conversation` — the listener-side glue that
    evaluates conditions and dispatches to the shared
    :class:`app.domains.automation.actions.ActionExecutor`. The actual
    listener wiring (which dispatcher events trigger which event_name)
    lands in 6.4.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.automation.actions import ActionExecutor
from app.domains.automation.conditions import evaluate_conditions
from app.domains.automation.models import (
    AUTOMATION_FILTER_OPERATORS,
    AUTOMATION_QUERY_OPERATORS,
    AUTOMATION_RULE_EVENTS,
    AUTOMATION_STANDARD_CONDITION_KEYS,
    AutomationRule,
    automation_allowed_actions,
)
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation, Message
from app.domains.custom_attributes.models import (
    CUSTOM_ATTR_MODEL_CONTACT,
    CUSTOM_ATTR_MODEL_CONVERSATION,
    CustomAttributeDefinition,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate_event_name(raw: Any) -> str:
    if not isinstance(raw, str) or raw not in AUTOMATION_RULE_EVENTS:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"event_name must be one of: "
                    f"{', '.join(AUTOMATION_RULE_EVENTS)}"
                ),
            },
        )
    return raw


async def _custom_attribute_keys_for_account(
    session: AsyncSession, *, account_id: int
) -> set[str]:
    rows = list(
        (
            await session.exec(
                select(CustomAttributeDefinition).where(
                    CustomAttributeDefinition.account_id == account_id,
                    CustomAttributeDefinition.attribute_model.in_(
                        [
                            CUSTOM_ATTR_MODEL_CONVERSATION,
                            CUSTOM_ATTR_MODEL_CONTACT,
                        ]
                    ),
                )
            )
        ).all()
    )
    return {r.attribute_key for r in rows}


async def _validate_conditions(
    session: AsyncSession,
    *,
    account_id: int,
    raw: Any,
) -> list[dict[str, Any]]:
    """Mirror ``json_conditions_format`` + ``query_operator_*`` validators."""
    if raw is None or raw == []:
        return []
    if not isinstance(raw, list):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "conditions must be an array"},
        )

    custom_keys = await _custom_attribute_keys_for_account(
        session, account_id=account_id
    )
    cleaned: list[dict[str, Any]] = []
    bad_keys: list[str] = []
    null_query_op = 0

    for entry in raw:
        if not isinstance(entry, dict):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "each condition must be an object"},
            )
        attribute_key = entry.get("attribute_key")
        filter_operator = entry.get("filter_operator")
        query_operator = entry.get("query_operator")
        values = entry.get("values", [])
        custom_type = entry.get("custom_attribute_type")

        if not isinstance(attribute_key, str) or not attribute_key:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "each condition requires an attribute_key"
                },
            )
        if not isinstance(filter_operator, str) or filter_operator not in AUTOMATION_FILTER_OPERATORS:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": (
                        f"filter_operator must be one of: "
                        f"{', '.join(AUTOMATION_FILTER_OPERATORS)}"
                    ),
                },
            )

        # ``query_operator_value`` validation: when present, must be
        # AND or OR (case-insensitive).
        if query_operator is not None and query_operator != "":
            if not isinstance(query_operator, str) or query_operator.upper() not in AUTOMATION_QUERY_OPERATORS:
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": 'Query operator must be either "AND" or "OR"'
                    },
                )
        else:
            null_query_op += 1

        # Attribute key allowlist: standard set OR custom-attribute key
        # for the account.
        if (
            attribute_key not in AUTOMATION_STANDARD_CONDITION_KEYS
            and attribute_key not in custom_keys
        ):
            bad_keys.append(attribute_key)
            continue

        if not isinstance(values, list):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "values must be an array"},
            )

        cleaned_entry: dict[str, Any] = {
            "attribute_key": attribute_key,
            "filter_operator": filter_operator,
            "query_operator": (
                (query_operator.upper() if isinstance(query_operator, str) else "")
                if query_operator
                else ""
            ),
            "values": values,
        }
        if custom_type:
            cleaned_entry["custom_attribute_type"] = custom_type
        cleaned.append(cleaned_entry)

    if bad_keys:
        # Match Rails' exact error string.
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"Automation conditions {','.join(bad_keys)} not supported."
                ),
            },
        )
    # Rails: ``operators.length > 1`` triggers — only one entry can have
    # an empty query_operator (the LAST one).
    if null_query_op > 1:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "Automation conditions should have query operator."
            },
        )
    return cleaned


def _validate_actions(raw: Any) -> list[dict[str, Any]]:
    """Mirror ``AutomationRule#json_actions_format`` (similar to Macro
    but with the extra send_email_to_team / open_conversation /
    pending_conversation actions)."""
    if raw is None or raw == []:
        return []
    if not isinstance(raw, list):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "actions must be an array"},
        )
    allowed = automation_allowed_actions()
    cleaned: list[dict[str, Any]] = []
    bad: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "each action must be an object"},
            )
        name = entry.get("action_name")
        if not isinstance(name, str) or not name:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "each action requires action_name"},
            )
        if name not in allowed:
            bad.append(name)
            continue
        params = entry.get("action_params", [])
        if params is None:
            params = []
        if not isinstance(params, list):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "action_params must be an array"},
            )
        cleaned.append({"action_name": name, "action_params": params})

    if bad:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": f"Automation actions {','.join(bad)} not supported."
            },
        )
    return cleaned


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def list_rules(
    session: AsyncSession, *, account_id: int
) -> list[AutomationRule]:
    return list(
        (
            await session.exec(
                select(AutomationRule)
                .where(AutomationRule.account_id == account_id)
                .order_by(AutomationRule.id.desc())
            )
        ).all()
    )


async def fetch_rule(
    session: AsyncSession, *, account_id: int, rule_id: int
) -> AutomationRule | None:
    return (
        await session.exec(
            select(AutomationRule).where(
                AutomationRule.id == rule_id,
                AutomationRule.account_id == account_id,
            )
        )
    ).first()


async def create_rule(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> AutomationRule:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Name can't be blank"}
        )
    event_name = _validate_event_name(payload.get("event_name"))
    conditions = await _validate_conditions(
        session, account_id=account_id, raw=payload.get("conditions")
    )
    actions = _validate_actions(payload.get("actions"))
    active_raw = payload.get("active", True)
    active = bool(active_raw) if active_raw is not None else True

    rule = AutomationRule(
        account_id=account_id,
        name=name,
        description=payload.get("description"),
        event_name=event_name,
        active=active,
        conditions=conditions,
        actions=actions,
    )
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return rule


async def update_rule(
    session: AsyncSession,
    *,
    rule: AutomationRule,
    payload: dict[str, Any],
) -> AutomationRule:
    if "name" in payload:
        new_name = (payload.get("name") or "").strip()
        if not new_name:
            raise ChatwootHTTPException(
                status_code=422, detail={"message": "Name can't be blank"}
            )
        rule.name = new_name
    if "description" in payload:
        rule.description = payload.get("description")
    if "event_name" in payload:
        rule.event_name = _validate_event_name(payload.get("event_name"))
    if "active" in payload:
        active_raw = payload.get("active")
        rule.active = bool(active_raw) if active_raw is not None else True
    if "conditions" in payload:
        rule.conditions = await _validate_conditions(
            session,
            account_id=rule.account_id,
            raw=payload.get("conditions"),
        )
    if "actions" in payload:
        rule.actions = _validate_actions(payload.get("actions"))

    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return rule


async def destroy_rule(session: AsyncSession, *, rule: AutomationRule) -> None:
    await session.delete(rule)
    await session.flush()


async def clone_rule(
    session: AsyncSession, *, rule: AutomationRule
) -> AutomationRule:
    """Mirror ``AutomationRulesController#clone`` — ``automation_rule.dup``
    produces a brand-new row with the same fields except ``id`` /
    ``created_at`` / ``updated_at``."""
    cloned = AutomationRule(
        account_id=rule.account_id,
        name=rule.name,
        description=rule.description,
        event_name=rule.event_name,
        active=rule.active,
        conditions=copy.deepcopy(rule.conditions),
        actions=copy.deepcopy(rule.actions),
    )
    session.add(cloned)
    await session.flush()
    await session.refresh(cloned)
    return cloned


# ---------------------------------------------------------------------------
# Listener-side execution
# ---------------------------------------------------------------------------
async def run_rule_on_conversation(
    session: AsyncSession,
    *,
    rule: AutomationRule,
    conversation: Conversation,
    message: Message | None = None,
) -> bool:
    """Evaluate ``rule.conditions`` and run actions if they match.

    Returns True when the actions were executed, False when conditions
    didn't match (or when the rule is inactive). The 6.4 listeners
    will call this from the dispatcher hooks.
    """
    if not rule.active:
        return False

    contact: Contact | None = None
    if conversation.contact_id is not None:
        contact = await session.get(Contact, conversation.contact_id)

    matched = evaluate_conditions(
        list(rule.conditions or []),
        conversation=conversation,
        message=message,
        contact=contact,
    )
    if not matched:
        return False

    executor = ActionExecutor(session, conversation=conversation)
    await executor.execute(list(rule.actions or []))
    return True


__all__ = [
    "clone_rule",
    "create_rule",
    "destroy_rule",
    "fetch_rule",
    "list_rules",
    "run_rule_on_conversation",
    "update_rule",
]
