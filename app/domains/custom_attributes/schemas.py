"""Request bodies for ``/custom_attribute_definitions``.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/custom_attribute_definitions_controller.rb

``params.require(:custom_attribute_definition).permit(...)`` wraps every
mutating request in a top-level ``custom_attribute_definition`` object.
We model the envelope and the inner body separately so the router does
exactly one ``.model_validate`` call.

``attribute_model`` and ``attribute_display_type`` are accepted as
Rails *string* enum values (``"conversation_attribute"``, ``"list"``)
because that's what Chatwoot's frontend sends and what jbuilder
renders. The service layer coerces those strings to integer columns
via the model-level helpers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Chatwoot's enum string keys — duplicated as Literal[...] so Pydantic
# can reject unknown values at parse time. The model layer owns the
# canonical int ↔ string mapping (see :mod:`app.domains.custom_attributes.models`).
AttributeModelLiteral = Literal["conversation_attribute", "contact_attribute"]

AttributeDisplayTypeLiteral = Literal[
    "text",
    "number",
    "currency",
    "percent",
    "link",
    "date",
    "list",
    "checkbox",
]


class _CustomAttributeDefinitionBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    attribute_display_name: str | None = None
    attribute_description: str | None = None
    attribute_display_type: AttributeDisplayTypeLiteral | None = None
    attribute_key: str | None = None
    attribute_model: AttributeModelLiteral | None = None
    regex_pattern: str | None = None
    regex_cue: str | None = None
    attribute_values: list[Any] = Field(default_factory=list)


class CustomAttributeDefinitionEnvelope(BaseModel):
    """Mirrors ``params.require(:custom_attribute_definition)``.

    Same shape for create + update; the service layer enforces which
    fields are editable post-create (``attribute_key`` is effectively
    locked — see the service's update path).
    """

    model_config = ConfigDict(extra="ignore")

    custom_attribute_definition: _CustomAttributeDefinitionBody


__all__ = [
    "AttributeDisplayTypeLiteral",
    "AttributeModelLiteral",
    "CustomAttributeDefinitionEnvelope",
]
