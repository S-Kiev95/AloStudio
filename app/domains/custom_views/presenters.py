"""Wire-shape presenter for CustomView.

``filter_type`` is emitted as the enum string (Rails' jbuilder calls
``custom_view.filter_type`` which returns the enum name).
"""

from __future__ import annotations

from typing import Any

from app.domains.custom_views.models import CustomView, custom_view_type_to_str


def present_custom_view(view: CustomView) -> dict[str, Any]:
    return {
        "id": view.id,
        "name": view.name,
        "filter_type": custom_view_type_to_str(view.filter_type),
        "query": view.query,
        "created_at": view.created_at,
        "updated_at": view.updated_at,
    }


__all__ = ["present_custom_view"]
