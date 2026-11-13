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
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
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
# What the sync keeps of each template: enough to send it, and for the
# management screen its state and why Meta rejected it.
_TEMPLATE_FIELDS = "id,name,language,status,category,components,rejected_reason,quality_score"


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
    message: Message | None,
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
    message: Message | None,
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
    message: Message | None,
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
    message: Message | None,
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
    # ``message`` is None for sends that aren't a chat message (team
    # notices): nothing to thread the delivery status onto.
    if msg_id and message is not None:
        message.source_id = str(msg_id)
        session.add(message)
        await session.flush()
    log.info(
        "whatsapp.send_template.%s.ok channel_id=%s message_id=%s remote_id=%s",
        log_prefix,
        channel.id,
        message.id if message is not None else None,
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
        f"&fields={_TEMPLATE_FIELDS}"
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


# ---------------------------------------------------------------------------
# Manage templates (F5): create, edit and delete on Meta
# ---------------------------------------------------------------------------
TEMPLATE_CATEGORIES = ("MARKETING", "UTILITY", "AUTHENTICATION")
_TEMPLATE_NAME_RE = re.compile(r"^[a-z0-9_]{1,512}$")


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


def _waba(channel: WhatsappChannel) -> tuple[str, str]:
    """``(business_account_id, api_key)`` of a Cloud channel, or 422."""
    cfg = channel.provider_config if isinstance(channel.provider_config, dict) else {}
    waba, token = cfg.get("business_account_id"), cfg.get("api_key")
    if channel.provider != WHATSAPP_PROVIDER_CLOUD or not waba or not token:
        raise _unprocessable(
            "Las plantillas se administran solo en bandejas de WhatsApp Cloud "
            "conectadas a una cuenta de WhatsApp Business."
        )
    return str(waba), str(token)


async def _graph_call(
    channel: WhatsappChannel,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the Graph API with the channel's token; Meta's own message on
    failure (it explains what is wrong with the template)."""
    _, token = _waba(channel)
    url = f"{_cloud_api_base()}/{get_settings().meta_graph_api_version}/{path}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.request(
                method,
                url,
                params=params,
                json=json,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.HTTPError as exc:
        raise _unprocessable("Meta no respondió. Probá de nuevo en un rato.") from exc
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code >= 400 or not isinstance(body, dict):
        error = body.get("error") if isinstance(body, dict) else None
        detail = None
        if isinstance(error, dict):
            detail = error.get("error_user_msg") or error.get("message")
        log.warning(
            "whatsapp.templates.api_error channel_id=%s path=%s status=%s body=%s",
            channel.id,
            path,
            resp.status_code,
            resp.text[:300],
        )
        raise _unprocessable(detail or "Meta rechazó el pedido.")
    return body


def _check_components(components: Any) -> list[dict[str, Any]]:
    if not isinstance(components, list) or not all(isinstance(c, dict) for c in components):
        raise _unprocessable("components tiene que ser una lista de objetos.")
    if not any(str(c.get("type", "")).upper() == "BODY" for c in components):
        raise _unprocessable("La plantilla necesita un cuerpo (BODY).")
    return components


async def create_template(
    session: AsyncSession, *, channel: WhatsappChannel, payload: dict[str, Any]
) -> dict[str, Any]:
    """Submit a new template to Meta for review, then refresh the cache.
    Returns Meta's answer (``id``, ``status``, ``category``)."""
    waba, _ = _waba(channel)
    name = str(payload.get("name") or "").strip()
    if not _TEMPLATE_NAME_RE.match(name):
        raise _unprocessable(
            "El nombre va en minúsculas, sin espacios: letras, números y guiones bajos."
        )
    category = str(payload.get("category") or "").upper()
    if category not in TEMPLATE_CATEGORIES:
        raise _unprocessable("La categoría es MARKETING, UTILITY o AUTHENTICATION.")
    language = str(payload.get("language") or "").strip()
    if not language:
        raise _unprocessable("Falta el idioma (por ejemplo es o es_AR).")
    body = await _graph_call(
        channel,
        "POST",
        f"{waba}/message_templates",
        json={
            "name": name,
            "category": category,
            "language": language,
            "components": _check_components(payload.get("components")),
        },
    )
    await sync_templates(session, channel=channel)
    return body


async def edit_template(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    template_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Change an existing template's components (and category). Meta sends
    it back to review; an approved one can be edited a few times a day."""
    _waba(channel)
    body: dict[str, Any] = {"components": _check_components(payload.get("components"))}
    category = payload.get("category")
    if category:
        if str(category).upper() not in TEMPLATE_CATEGORIES:
            raise _unprocessable("La categoría es MARKETING, UTILITY o AUTHENTICATION.")
        body["category"] = str(category).upper()
    result = await _graph_call(channel, "POST", template_id, json=body)
    await sync_templates(session, channel=channel)
    return result


async def delete_template(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    name: str,
    template_id: str | None = None,
) -> None:
    """Delete a template on Meta (one language when ``template_id`` is given,
    every language of ``name`` otherwise) and drop it from the cache."""
    waba, _ = _waba(channel)
    params: dict[str, Any] = {"name": name}
    if template_id:
        params["hsm_id"] = template_id
    await _graph_call(channel, "DELETE", f"{waba}/message_templates", params=params)
    channel.message_templates = [
        t
        for t in channel.message_templates or []
        if not (
            isinstance(t, dict)
            and t.get("name") == name
            and (not template_id or str(t.get("id")) == str(template_id))
        )
    ]
    session.add(channel)
    await session.flush()


async def apply_template_update(
    session: AsyncSession, *, channel: WhatsappChannel, field: str, value: dict[str, Any]
) -> int:
    """Webhook ``message_template_status_update`` / ``template_category_update``:
    update the cached template on every Cloud channel of the same WhatsApp
    Business Account. Returns how many channels changed."""
    from sqlmodel import select

    template_id = str(value.get("message_template_id") or "")
    if not template_id:
        return 0
    cfg = channel.provider_config if isinstance(channel.provider_config, dict) else {}
    waba = cfg.get("business_account_id")
    channels = [channel]
    if waba:
        table = WhatsappChannel.__table__  # type: ignore[attr-defined]
        channels = list(
            (
                await session.exec(
                    select(WhatsappChannel).where(
                        WhatsappChannel.account_id == channel.account_id,
                        WhatsappChannel.provider == WHATSAPP_PROVIDER_CLOUD,
                        table.c.provider_config["business_account_id"].astext == str(waba),
                    )
                )
            ).all()
        ) or [channel]
    changed = 0
    for ch in channels:
        templates = [dict(t) for t in ch.message_templates or [] if isinstance(t, dict)]
        hit = False
        for tpl in templates:
            if str(tpl.get("id")) != template_id:
                continue
            hit = True
            if field == "message_template_status_update" and value.get("event"):
                tpl["status"] = str(value["event"]).upper()
                reason = value.get("reason")
                tpl["rejected_reason"] = reason if reason and reason != "NONE" else None
            elif field == "template_category_update" and value.get("new_category"):
                tpl["category"] = str(value["new_category"]).upper()
        if hit:
            ch.message_templates = templates
            session.add(ch)
            changed += 1
    if changed:
        await session.flush()
    log.info(
        "whatsapp.templates.webhook field=%s template_id=%s channels=%s",
        field,
        template_id,
        changed,
    )
    return changed


__all__ = [
    "TEMPLATE_CATEGORIES",
    "apply_template_update",
    "create_template",
    "delete_template",
    "edit_template",
    "send_template_message",
    "sync_templates",
    "template_body_parameters",
]
