"""Wire-shape presenters for IntegrationsHook + IntegrationApp.

Anchors:
  reference/chatwoot/app/views/api/v1/models/_hook.json.jbuilder
  reference/chatwoot/app/views/api/v1/models/_app.json.jbuilder
"""

from __future__ import annotations

from typing import Any

from app.domains.inboxes.models import Inbox
from app.domains.integrations.models import (
    HOOK_STATUS_ENABLED,
    IntegrationApp,
    IntegrationsHook,
    hook_type_to_str,
)


def present_hook(
    hook: IntegrationsHook,
    *,
    inbox: Inbox | None = None,
    show_admin_fields: bool = False,
) -> dict[str, Any]:
    """Mirror ``_hook.json.jbuilder``."""
    body: dict[str, Any] = {
        "id": hook.id,
        "app_id": hook.app_id,
        "status": hook.status == HOOK_STATUS_ENABLED,
        "account_id": hook.account_id,
        "hook_type": hook_type_to_str(hook.hook_type),
    }
    body["inbox"] = (
        {"id": inbox.id, "name": inbox.name} if inbox is not None else None
    )
    if show_admin_fields:
        body["settings"] = hook.settings or {}
        body["reference_id"] = hook.reference_id
    return body


def present_app(
    app: IntegrationApp,
    *,
    account_hooks: list[IntegrationsHook],
    show_admin_fields: bool = False,
) -> dict[str, Any]:
    """Mirror ``_app.json.jbuilder``.

    ``hooks`` is the array of this account's hooks scoped to the app."""
    body: dict[str, Any] = {
        "id": app.id,
        "name": app.name,
        "description": app.description,
        "short_description": app.short_description,
        "enabled": app.enabled,
    }
    if show_admin_fields:
        body["allow_multiple_hooks"] = app.allow_multiple_hooks
    body["hooks"] = [
        present_hook(h, show_admin_fields=show_admin_fields)
        for h in account_hooks
        if h.app_id == app.id
    ]
    return body


__all__ = ["present_app", "present_hook"]
