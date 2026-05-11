"""Pydantic schemas for the CSAT endpoints.

Anchors:
  reference/chatwoot/app/controllers/public/api/v1/csat_survey_controller.rb
    (params.permit(message: [{ submitted_values: [...,
       { csat_survey_response: [:feedback_message, :rating] }] }]))
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CsatResponseBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rating: int
    feedback_message: str | None = None


class CsatSubmittedValueEntry(BaseModel):
    """One entry in ``submitted_values`` — Chatwoot stuffs the response
    payload under the entry whose ``value`` matches the chosen rating
    (the others are inert). We accept the outer envelope as a list and
    pull the first ``csat_survey_response`` we find."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    title: str | None = None
    value: int | str | None = None
    csat_survey_response: CsatResponseBody | None = None


class CsatMessageBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    submitted_values: list[CsatSubmittedValueEntry] = []


class CsatUpdateEnvelope(BaseModel):
    """Top-level body for ``PUT /public/api/v1/csat_survey/{uuid}``.

    Mirrors ``params.permit(message: ...)``."""

    model_config = ConfigDict(extra="ignore")

    message: CsatMessageBody


__all__ = [
    "CsatMessageBody",
    "CsatResponseBody",
    "CsatSubmittedValueEntry",
    "CsatUpdateEnvelope",
]
