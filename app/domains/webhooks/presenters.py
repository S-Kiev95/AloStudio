"""Wire-shape presenters for Webhook.

Anchors:
  reference/chatwoot/app/views/api/v1/accounts/webhooks/_webhook.json.jbuilder
  reference/chatwoot/app/views/api/v1/accounts/webhooks/{index,create,update}.json.jbuilder
"""

from __future__ import annotations

from typing import Any

from app.domains.inboxes.models import Inbox
from app.domains.webhooks.models import Webhook


def present_webhook(
    webhook: Webhook,
    *,
    inbox: Inbox | None = None,
) -> dict[str, Any]:
    """Mirror ``_webhook.json.jbuilder``."""
    body: dict[str, Any] = {
        "id": webhook.id,
        "name": webhook.name,
        "url": webhook.url,
        "account_id": webhook.account_id,
        "subscriptions": list(webhook.subscriptions or []),
        "secret": webhook.secret,
    }
    if inbox is not None:
        body["inbox"] = {"id": inbox.id, "name": inbox.name}
    return body


def envelope_index(bodies: list[dict[str, Any]]) -> dict[str, Any]:
    return {"payload": {"webhooks": bodies}}


def envelope_one(body: dict[str, Any]) -> dict[str, Any]:
    return {"payload": {"webhook": body}}


__all__ = ["envelope_index", "envelope_one", "present_webhook"]
