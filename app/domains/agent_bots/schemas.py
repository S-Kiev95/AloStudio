"""Pydantic schemas for AgentBot CRUD.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/agent_bots_controller.rb
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentBotPayload(BaseModel):
    """Body for create / update.

    Mirrors ``params.permit(:name, :description, :outgoing_url,
    :avatar, :avatar_url, :bot_type, bot_config: {})``. ``bot_type``
    is enum-validated at the service boundary (only ``webhook`` is
    supported in v4.13.0)."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    description: str | None = None
    outgoing_url: str | None = None
    bot_config: dict[str, Any] | None = None


class SetAgentBotPayload(BaseModel):
    """Body for ``POST /inboxes/{id}/set_agent_bot``."""

    model_config = ConfigDict(extra="ignore")

    agent_bot: int | None = None


__all__ = ["AgentBotPayload", "SetAgentBotPayload"]
