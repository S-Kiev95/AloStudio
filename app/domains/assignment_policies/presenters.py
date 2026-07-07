"""Wire-shape presenter for AssignmentPolicy.

Emits the int enums as their string names (``assignment_order`` /
``conversation_priority``). Single resources are bare objects; the index is
a bare array.
"""

from __future__ import annotations

from typing import Any

from app.domains.assignment_policies.models import (
    AssignmentPolicy,
    assignment_order_to_str,
    conversation_priority_to_str,
)


def present_assignment_policy(policy: AssignmentPolicy) -> dict[str, Any]:
    return {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "enabled": policy.enabled,
        "assignment_order": assignment_order_to_str(policy.assignment_order),
        "conversation_priority": conversation_priority_to_str(
            policy.conversation_priority
        ),
        "fair_distribution_limit": policy.fair_distribution_limit,
        "fair_distribution_window": policy.fair_distribution_window,
    }


def present_assignment_policies(
    policies: list[AssignmentPolicy],
) -> list[dict[str, Any]]:
    return [present_assignment_policy(p) for p in policies]


__all__ = ["present_assignment_policies", "present_assignment_policy"]
