"""Wire-shape renderer for CustomAttributeDefinition.

Mirrors ``reference/chatwoot/app/views/api/v1/models/_custom_attribute_definition.json.jbuilder``.

Chatwoot emits ``created_at`` / ``updated_at`` as ISO-8601 strings here
(no ``.to_i``), unlike the Contact jbuilder. We replicate that — the
frontend consumes the two shapes inconsistently, so parity requires we
keep the inconsistency.
"""

from __future__ import annotations

from typing import Any

from app.domains.custom_attributes.models import CustomAttributeDefinition


def _iso(dt: Any) -> str | None:
    return None if dt is None else dt.isoformat()


def present_definition(definition: CustomAttributeDefinition) -> dict[str, Any]:
    return {
        "id": definition.id,
        "attribute_display_name": definition.attribute_display_name,
        "attribute_display_type": definition.attribute_display_type_str,
        "attribute_description": definition.attribute_description,
        "attribute_key": definition.attribute_key,
        "regex_pattern": definition.regex_pattern,
        "regex_cue": definition.regex_cue,
        "attribute_values": definition.attribute_values or [],
        "attribute_model": definition.attribute_model_str,
        "default_value": definition.default_value,
        "created_at": _iso(definition.created_at),
        "updated_at": _iso(definition.updated_at),
    }


def present_definitions_index(
    definitions: list[CustomAttributeDefinition],
) -> list[dict[str, Any]]:
    """Top-level JSON array — matches ``index.json.jbuilder``."""
    return [present_definition(d) for d in definitions]


__all__ = ["present_definition", "present_definitions_index"]
