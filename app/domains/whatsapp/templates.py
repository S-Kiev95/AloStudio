"""WhatsApp message templates — sync + send.

Ported from:
  reference/chatwoot/app/services/whatsapp/providers/whatsapp_cloud_service.rb
  reference/chatwoot/app/services/whatsapp/providers/whatsapp_360_dialog_service.rb
  (the ``send_template`` + ``sync_templates`` halves of each)

Templates are pre-approved message bodies (Meta calls them "Highly
Structured Messages") that an agent can send to a contact even
outside the 24-hour customer service window. Each template has:

  * A ``name`` (e.g. ``order_shipped``).
  * A ``language`` code (``en_US``, ``es_AR``, …).
  * A list of ``components`` — header, body, footer, buttons —
    each carrying parameter placeholders (``{{1}}``, ``{{2}}``, …)
    that the caller fills in at send time.

5c.6.b scope:
  * ``sync_templates`` — fetch the approved templates from Graph
    (Cloud) or 360dialog and store under
    ``WhatsappChannel.message_templates``. Cloud paginates (``paging
    .next``), 360dialog doesn't.
  * ``send_template_message`` — POST a ``type=template`` body with
    pre-built ``components`` to the right provider URL.

Deferred to later phases:
  * CSAT template create/update + ``template_processor_service`` (the
    ``{{1}}`` -> agent-supplied value substitution helper Chatwoot
    runs before send) — Phase 9.
  * Authentication templates (``otp_buttons``) — same.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Message
from app.domains.inboxes.models import (
    WHATSAPP_PROVIDER_360DIALOG,
    WHATSAPP_PROVIDER_CLOUD,
    WhatsappChannel,
)
from app.domains.whatsapp.cloud_provider import (
    _PHONE_ID_API_VERSION,
)
from app.domains.whatsapp.cloud_provider import (
    _api_base as _cloud_api_base,
)
from app.domains.whatsapp.cloud_provider import (
    _api_headers as _cloud_api_headers,
)
from app.domains.whatsapp.dialog360_provider import (
    _api_base as _d360_api_base,
)
from app.domains.whatsapp.dialog360_provider import (
    _api_headers as _d360_api_headers,
)

log = logging.getLogger(__name__)


# Cloud's business-account templates endpoint uses v14.0 (Rails uses
# the same hard-coded version). The phone-id path uses v13.0 — keep
# them in sync with the reference so a real Graph call validates
# against the same Meta-side schema.
_BUSINESS_API_VERSION = "v14.0"


# ---------------------------------------------------------------------------
# Template body construction
# ---------------------------------------------------------------------------
def template_body_parameters(template_info: dict[str, Any]) -> dict[str, Any]:
    """Build the ``template`` field for a WhatsApp send request.

    Mirrors Rails' ``template_body_parameters``. Input shape:

        {
          "name": "order_shipped",
          "lang_code": "en_US",
          "parameters": [
            {"type": "body", "parameters": [{"type": "text", "text": "..."}]},
            {"type": "header", ...},
          ]
        }

    Output (the WhatsApp ``template`` object):

        {
          "name": "order_shipped",
          "language": {"policy": "deterministic", "code": "en_US"},
          "components": [...]
        }

    The ``policy: deterministic`` field tells Meta to refuse the
    send if the requested language doesn't exactly match an
    approved variant of the template (instead of falling back to
    a different language). Chatwoot uses this exact policy.
    """
    return {
        "name": template_info.get("name"),
        "language": {
            "policy": "deterministic",
            "code": template_info.get("lang_code"),
        },
        "components": template_info.get("parameters") or [],
    }


# ---------------------------------------------------------------------------
# Send template
# ---------------------------------------------------------------------------
async def send_template_message(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    message: Message,
    to_phone: str,
    template_info: dict[str, Any],
) -> bool:
    """Send a template message via the channel's provider.

    Returns True on success, False otherwise (logged but never
    raised). On success ``message.source_id`` carries the remote
    message id for status threading.

    ``template_info`` contract — see :func:`template_body_parameters`.
    """
    provider = channel.provider
    if provider == WHATSAPP_PROVIDER_CLOUD:
        return await _send_template_cloud(
            session,
            channel=channel,
            message=message,
            to_phone=to_phone,
            template_info=template_info,
        )
    if provider == WHATSAPP_PROVIDER_360DIALOG:
        return await _send_template_360dialog(
            session,
            channel=channel,
            message=message,
            to_phone=to_phone,
            template_info=template_info,
        )
    log.warning(
        "whatsapp.send_template.unknown_provider channel_id=%s provider=%s",
        channel.id,
        provider,
    )
    return False


async def _send_template_cloud(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    message: Message,
    to_phone: str,
    template_info: dict[str, Any],
) -> bool:
    cfg = channel.provider_config or {}
    if not isinstance(cfg, dict) or not cfg.get("api_key") or not cfg.get(
        "phone_number_id"
    ):
        log.warning(
            "whatsapp.send_template.cloud.skip_config channel_id=%s",
            channel.id,
        )
        return False

    body: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "template",
        "template": template_body_parameters(template_info),
    }
    url = (
        f"{_cloud_api_base()}/{_PHONE_ID_API_VERSION}/"
        f"{cfg['phone_number_id']}/messages"
    )
    return await _post_and_stamp(
        session,
        channel=channel,
        message=message,
        url=url,
        headers=_cloud_api_headers(channel),
        body=body,
        log_prefix="cloud",
    )


async def _send_template_360dialog(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    message: Message,
    to_phone: str,
    template_info: dict[str, Any],
) -> bool:
    cfg = channel.provider_config or {}
    if not isinstance(cfg, dict) or not cfg.get("api_key"):
        log.warning(
            "whatsapp.send_template.360d.skip_config channel_id=%s",
            channel.id,
        )
        return False

    body: dict[str, Any] = {
        "to": to_phone,
        "type": "template",
        "template": template_body_parameters(template_info),
    }
    url = f"{_d360_api_base(channel)}/messages"
    return await _post_and_stamp(
        session,
        channel=channel,
        message=message,
        url=url,
        headers=_d360_api_headers(channel),
        body=body,
        log_prefix="360d",
    )


async def _post_and_stamp(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    message: Message,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    log_prefix: str,
) -> bool:
    """Shared HTTP + WAMID-stamp dance.

    Both providers return ``{"messages": [{"id": "..."}]}`` on success;
    the stamp lookup is identical. We swallow transport / 4xx / 5xx
    errors to keep the post-create cascade safe.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "whatsapp.send_template.%s.transport_error channel_id=%s err=%s",
            log_prefix,
            channel.id,
            exc,
        )
        return False
    if resp.status_code >= 400:
        log.warning(
            "whatsapp.send_template.%s.api_error channel_id=%s status=%s body=%s",
            log_prefix,
            channel.id,
            resp.status_code,
            resp.text[:500],
        )
        return False
    try:
        payload = resp.json()
    except ValueError:
        return False
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list) or not messages:
        return False
    msg_id = messages[0].get("id") if isinstance(messages[0], dict) else None
    if msg_id:
        message.source_id = str(msg_id)
        session.add(message)
        await session.flush()
    log.info(
        "whatsapp.send_template.%s.ok channel_id=%s message_id=%s remote_id=%s",
        log_prefix,
        channel.id,
        message.id,
        msg_id,
    )
    return True


# ---------------------------------------------------------------------------
# Sync templates
# ---------------------------------------------------------------------------
async def sync_templates(
    session: AsyncSession, *, channel: WhatsappChannel
) -> int:
    """Fetch + store the channel's approved templates.

    Returns the count of templates stored. Exceptions / non-2xx
    responses leave the existing list untouched + log a warning.
    Mirrors Rails: a sync that fails for any reason still bumps the
    ``message_templates_last_updated`` timestamp so we don't keep
    retrying the same broken config in a tight loop.
    """
    # Stamp the timestamp first (mirrors mark_message_templates_updated).
    channel.message_templates_last_updated = datetime.now(UTC)

    if channel.provider == WHATSAPP_PROVIDER_CLOUD:
        templates = await _fetch_cloud_templates(channel)
    elif channel.provider == WHATSAPP_PROVIDER_360DIALOG:
        templates = await _fetch_360dialog_templates(channel)
    else:
        templates = []

    if templates:
        channel.message_templates = templates
    session.add(channel)
    await session.flush()
    return len(templates)


async def _fetch_cloud_templates(
    channel: WhatsappChannel,
) -> list[dict[str, Any]]:
    """Walk Meta's paginated ``message_templates`` endpoint.

    Mirrors Rails ``fetch_whatsapp_templates`` recursion via a flat
    loop. Caps pagination at 100 pages defensively (Meta paginates
    at 25/page so 100 pages = 2500 templates, more than any real
    deployment ships).
    """
    cfg = channel.provider_config or {}
    if not isinstance(cfg, dict):
        return []
    api_key = cfg.get("api_key")
    business_account_id = cfg.get("business_account_id")
    if not api_key or not business_account_id:
        return []

    url: str | None = (
        f"{_cloud_api_base()}/{_BUSINESS_API_VERSION}/"
        f"{business_account_id}/message_templates"
        f"?access_token={api_key}"
    )
    out: list[dict[str, Any]] = []
    pages_walked = 0
    async with httpx.AsyncClient(timeout=15.0) as client:
        while url and pages_walked < 100:
            try:
                resp = await client.get(url)
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                log.warning(
                    "whatsapp.sync_templates.cloud.transport_error "
                    "channel_id=%s err=%s",
                    channel.id,
                    exc,
                )
                return out
            if resp.status_code >= 400:
                log.warning(
                    "whatsapp.sync_templates.cloud.api_error "
                    "channel_id=%s status=%s",
                    channel.id,
                    resp.status_code,
                )
                return out
            try:
                body = resp.json()
            except ValueError:
                return out
            data = body.get("data") if isinstance(body, dict) else None
            if isinstance(data, list):
                out.extend(d for d in data if isinstance(d, dict))
            paging = body.get("paging") if isinstance(body, dict) else None
            url = (
                paging.get("next")
                if isinstance(paging, dict)
                else None
            )
            pages_walked += 1
    return out


async def _fetch_360dialog_templates(
    channel: WhatsappChannel,
) -> list[dict[str, Any]]:
    """360dialog's templates endpoint returns the full list in one
    response (no pagination)."""
    cfg = channel.provider_config or {}
    if not isinstance(cfg, dict) or not cfg.get("api_key"):
        return []
    url = f"{_d360_api_base(channel)}/configs/templates"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=_d360_api_headers(channel))
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "whatsapp.sync_templates.360d.transport_error "
            "channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return []
    if resp.status_code >= 400:
        log.warning(
            "whatsapp.sync_templates.360d.api_error channel_id=%s status=%s",
            channel.id,
            resp.status_code,
        )
        return []
    try:
        body = resp.json()
    except ValueError:
        return []
    waba_templates = (
        body.get("waba_templates") if isinstance(body, dict) else None
    )
    if isinstance(waba_templates, list):
        return [d for d in waba_templates if isinstance(d, dict)]
    return []


__all__ = [
    "send_template_message",
    "sync_templates",
    "template_body_parameters",
]
