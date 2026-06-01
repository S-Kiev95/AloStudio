"""Pydantic schemas for the agents admin CRUD surface.

Chatwoot wraps the body in ``{"agent": {...}}``
(``params.require(:agent).permit(...)``); we mirror that on POST/PATCH
so the wire is identical.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RoleLiteral = Literal["agent", "administrator"]


class _AgentCreateBody(BaseModel):
    """The inner ``agent`` payload on ``POST /agents``."""

    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    role: RoleLiteral = "agent"
    availability: str | None = None  # mirrored on wire, currently no-op
    auto_offline: bool | None = None


class AgentCreateRequest(BaseModel):
    """Envelope for ``POST /agents`` — ``{"agent": {...}}``."""

    model_config = ConfigDict(extra="ignore")

    agent: _AgentCreateBody


class _AgentUpdateBody(BaseModel):
    """The inner ``agent`` payload on ``PATCH /agents/{id}`` — all fields optional."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: RoleLiteral | None = None
    availability: str | None = None
    auto_offline: bool | None = None


class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    agent: _AgentUpdateBody


__all__ = [
    "AgentCreateRequest",
    "AgentUpdateRequest",
    "RoleLiteral",
]
