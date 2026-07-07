"""Pydantic schemas for the AssignmentPolicy CRUD + inbox-link surface.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/assignment_policies_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/inboxes/assignment_policies_controller.rb
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AssignmentPolicyBody(BaseModel):
    """The ``assignment_policy`` hash. ``name`` is required on create
    (enforced in the service). ``assignment_order`` / ``conversation_priority``
    are the string enum names."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    assignment_order: str | None = None
    conversation_priority: str | None = None
    fair_distribution_limit: int | None = None
    fair_distribution_window: int | None = None


class AssignmentPolicyEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    assignment_policy: AssignmentPolicyBody


class InboxPolicyLinkBody(BaseModel):
    """``POST /inboxes/{id}/assignment_policy`` — flat ``assignment_policy_id``
    (Rails ``params.permit(:assignment_policy_id, :inbox_id)``)."""

    model_config = ConfigDict(extra="ignore")

    assignment_policy_id: int


__all__ = [
    "AssignmentPolicyBody",
    "AssignmentPolicyEnvelope",
    "InboxPolicyLinkBody",
]
