"""Pydantic schemas for the agent chat endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentMessageIn(BaseModel):
    """A message to the agent. Its length is checked by the service, so a
    too-long text gets a readable ``{"message"}`` like every other error."""

    model_config = ConfigDict(extra="ignore")

    content: str
    # The browser's IANA zone ("America/Montevideo"); UTC when missing.
    timezone: str | None = None
