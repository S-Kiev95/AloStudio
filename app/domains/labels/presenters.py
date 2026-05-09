"""Wire-shape presenters for Label.

Anchors:
  reference/chatwoot/app/views/api/v1/accounts/labels/{create,show,update,index}.json.jbuilder

The four jbuilder views emit the same five-field object — id / title /
description / color / show_on_sidebar — so we keep a single
:func:`present_label` helper. ``index`` wraps the array in a
``{"payload": [...]}`` envelope (mirrors the Rails view).
"""

from __future__ import annotations

from typing import Any

from app.domains.labels.models import Label


def present_label(label: Label) -> dict[str, Any]:
    """Mirrors the create/show/update jbuilder view byte-by-byte."""
    return {
        "id": label.id,
        "title": label.title,
        "description": label.description,
        "color": label.color,
        "show_on_sidebar": label.show_on_sidebar,
    }


def present_labels_index(labels: list[Label]) -> dict[str, Any]:
    """``GET /labels`` envelope: ``{"payload": [<label>, ...]}``."""
    return {"payload": [present_label(lab) for lab in labels]}


__all__ = ["present_label", "present_labels_index"]
