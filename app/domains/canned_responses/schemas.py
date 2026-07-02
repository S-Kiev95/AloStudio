"""Pydantic schemas for the CannedResponse CRUD surface.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/canned_responses_controller.rb
    (``params.require(:canned_response).permit(:short_code, :content)``)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CannedResponseBody(BaseModel):
    """The bare ``canned_response`` hash. Both fields are required on
    create (enforced in the service, mirroring Rails' presence
    validations) and optional on update."""

    model_config = ConfigDict(extra="ignore")

    short_code: str | None = None
    content: str | None = None


class CannedResponseEnvelope(BaseModel):
    """Top-level wrapper — mirrors ``params.require(:canned_response)``."""

    model_config = ConfigDict(extra="ignore")

    canned_response: CannedResponseBody


__all__ = ["CannedResponseBody", "CannedResponseEnvelope"]
