"""Pydantic schemas for the Macro CRUD surface.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/macros_controller.rb
    (params.permit(:name, :visibility, actions: [:action_name, { action_params: [] }]))
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

VisibilityLiteral = Literal["personal", "global"]


class MacroAction(BaseModel):
    """One entry in the Macro's ``actions`` array."""

    model_config = ConfigDict(extra="ignore")

    action_name: str
    action_params: list[Any] = Field(default_factory=list)


class MacroPayload(BaseModel):
    """Top-level body for create / update.

    Chatwoot's controller does NOT wrap the body in a ``macro: {...}``
    envelope — ``params.permit(:name, :visibility, actions: [...])``
    reads keys directly off the request body. We mirror that.
    """

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    visibility: VisibilityLiteral | None = None
    actions: list[dict[str, Any]] | None = None


class MacroExecutePayload(BaseModel):
    """Body for ``POST /macros/:id/execute``.

    Rails reads ``params[:conversation_ids]`` — a flat array."""

    model_config = ConfigDict(extra="ignore")

    conversation_ids: list[int] = Field(default_factory=list)


__all__ = [
    "MacroAction",
    "MacroExecutePayload",
    "MacroPayload",
    "VisibilityLiteral",
]
