"""Wire-shape presenters for AutomationRule.

Anchors:
  reference/chatwoot/app/views/api/v1/accounts/automation_rules/partials/_automation_rule.json.jbuilder
  reference/chatwoot/app/views/api/v1/accounts/automation_rules/{create,index,show,update,clone}.json.jbuilder

Note: ``create.json.jbuilder`` does NOT wrap in ``payload`` (it
renders the partial bare); index / show / update / clone DO wrap in
``payload``. Mirroring Chatwoot's accidental inconsistency to keep
clients happy.
"""

from __future__ import annotations

from typing import Any

from app.domains.automation.models import AutomationRule


def present_rule(rule: AutomationRule) -> dict[str, Any]:
    """Mirror ``_automation_rule.json.jbuilder``.

    ``created_on`` is an int unix timestamp (Rails ``.to_i``); we
    drop microseconds to match.
    """
    created_on = (
        int(rule.created_at.timestamp()) if rule.created_at else None
    )
    return {
        "id": rule.id,
        "account_id": rule.account_id,
        "name": rule.name,
        "description": rule.description,
        "event_name": rule.event_name,
        "conditions": list(rule.conditions or []),
        "actions": list(rule.actions or []),
        "created_on": created_on,
        "active": bool(rule.active),
    }


def envelope_payload(body: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    return {"payload": body}


__all__ = ["envelope_payload", "present_rule"]
