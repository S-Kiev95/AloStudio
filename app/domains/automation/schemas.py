"""Pydantic schemas for AutomationRule.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/automation_rules_controller.rb
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class AutomationRulePayload(BaseModel):
    """Body of create / update.

    Mirrors ``automation_rules_permit`` — keys are at the top level
    (no ``automation_rule: {...}`` envelope on input)."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    description: str | None = None
    event_name: str | None = None
    active: bool | None = None
    conditions: list[dict[str, Any]] | None = None
    actions: list[dict[str, Any]] | None = None


__all__ = ["AutomationRulePayload"]
