"""Meta's Conversions API for business messaging, WhatsApp side (F17).

* ``POST /{waba_id}/dataset`` gives the dataset linked to the WhatsApp
  Business Account (making one the first time).
* ``POST /{dataset_id}/events`` takes the events, each with the ad click's
  ``ctwa_clid``.

The number's own token is used: Meta asks it to carry
``whatsapp_business_management`` and ``whatsapp_business_manage_events``,
and the app to have Full Access to the Marketing API.

Docs: https://developers.facebook.com/docs/marketing-api/conversions-api/business-messaging
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD, WhatsappChannel
from app.domains.whatsapp.cloud_provider import _api_base as _cloud_api_base

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20.0
PARTNER_AGENT = "alostudio"


class ConversionsError(Exception):
    """``not_connected`` (no Cloud number with a business account and
    token), ``unreachable``, ``refused`` (Meta said no: ``detail``)."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def credentials(channel: WhatsappChannel) -> tuple[str, str]:
    """``(business account id, token)`` of a connected Cloud number."""
    cfg = channel.provider_config if isinstance(channel.provider_config, dict) else {}
    waba, token = cfg.get("business_account_id"), cfg.get("api_key")
    if channel.provider != WHATSAPP_PROVIDER_CLOUD or not waba or not token:
        raise ConversionsError("not_connected")
    return str(waba), str(token)


async def _post(path: str, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{_cloud_api_base()}/{get_settings().meta_graph_api_version}/{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        raise ConversionsError("unreachable") from exc
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400 or not isinstance(data, dict):
        error = data.get("error") if isinstance(data, dict) else None
        detail = None
        if isinstance(error, dict):
            detail = error.get("error_user_msg") or error.get("message")
        log.warning(
            "conversions.api_error path=%s status=%s body=%s",
            path.split("/")[-1],
            resp.status_code,
            resp.text[:300],
        )
        raise ConversionsError("refused", str(detail) if detail else None)
    return data


async def fetch_dataset(channel: WhatsappChannel) -> str:
    """The dataset linked to the number's business account."""
    waba, token = credentials(channel)
    body = await _post(f"{waba}/dataset", token)
    dataset = body.get("id") or body.get("dataset_id")
    if not dataset:
        raise ConversionsError("refused", "no dataset id")
    return str(dataset)


async def send_events(
    channel: WhatsappChannel, dataset_id: str, events: list[dict[str, Any]]
) -> dict[str, Any]:
    _, token = credentials(channel)
    return await _post(
        f"{dataset_id}/events", token, {"data": events, "partner_agent": PARTNER_AGENT}
    )


__all__ = ["ConversionsError", "credentials", "fetch_dataset", "send_events"]
