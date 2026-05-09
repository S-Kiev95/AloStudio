"""Wire-shape presenters for Macro.

Anchors:
  reference/chatwoot/app/views/api/v1/models/_macro.json.jbuilder
  reference/chatwoot/app/views/api/v1/accounts/macros/{create,show,update,index}.json.jbuilder

The four CRUD views all wrap the macro under a ``payload`` key:
  * single resource → ``{"payload": {...}}``
  * collection      → ``{"payload": [{...}, ...]}``

The bare macro object includes id / name / visibility / created_by /
updated_by / account_id / actions, plus ``files`` only when there are
attachments. We omit ``files`` entirely for 6.2 (deferred to Phase 10).
"""

from __future__ import annotations

from typing import Any

from app.domains.macros.models import Macro, macro_visibility_to_str


def present_macro(
    macro: Macro,
    *,
    created_by: dict[str, Any] | None = None,
    updated_by: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mirror ``_macro.json.jbuilder``.

    ``created_by`` / ``updated_by`` are pre-rendered agent partials
    (``_agent.json.jbuilder``) handed in by the caller — keeps the
    presenter pure (no DB lookups inside)."""
    body: dict[str, Any] = {
        "id": macro.id,
        "name": macro.name,
        "visibility": macro_visibility_to_str(macro.visibility),
    }
    if created_by is not None:
        body["created_by"] = created_by
    if updated_by is not None:
        body["updated_by"] = updated_by
    body["account_id"] = macro.account_id
    body["actions"] = list(macro.actions or [])
    return body


def envelope_one(macro_body: dict[str, Any]) -> dict[str, Any]:
    return {"payload": macro_body}


def envelope_index(macro_bodies: list[dict[str, Any]]) -> dict[str, Any]:
    return {"payload": macro_bodies}


__all__ = ["envelope_index", "envelope_one", "present_macro"]
