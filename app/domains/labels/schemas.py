"""Pydantic schemas for the Label CRUD surface.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/labels_controller.rb
    (params.require(:label).permit(:title, :description, :color, :show_on_sidebar))
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LabelBody(BaseModel):
    """The bare ``label`` hash. All four fields are optional on update;
    title is required on create but the service layer handles that
    consistently with Rails' presence validation."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    description: str | None = None
    color: str | None = None
    show_on_sidebar: bool | None = None


class LabelEnvelope(BaseModel):
    """Top-level wrapper — mirrors ``params.require(:label)``."""

    model_config = ConfigDict(extra="ignore")

    label: LabelBody


__all__ = ["LabelBody", "LabelEnvelope"]
