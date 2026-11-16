"""WhatsApp number management (F5): the number's state on Meta, the
business profile the contact sees, and QR codes / short links.

All of it goes to the Graph API with the channel's own token, through the
same helper the template management uses (Meta's message on failure).
Only WhatsApp Cloud channels: other providers answer 422.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import WhatsappChannel
from app.domains.whatsapp.cloud_provider import _api_base as _cloud_api_base
from app.domains.whatsapp.templates import _graph_call, _unprocessable, _waba

log = logging.getLogger(__name__)

_PHONE_FIELDS = (
    "display_phone_number,verified_name,quality_rating,name_status,status,"
    "code_verification_status,throughput,platform_type"
)
# Meta moved the daily limit around (per number, then per business); ask
# for each separately so a field it no longer knows doesn't fail the rest.
_LIMIT_FIELDS = ("whatsapp_business_manager_messaging_limit", "messaging_limit_tier")

PROFILE_FIELDS = (
    "about",
    "address",
    "description",
    "email",
    "websites",
    "vertical",
)
_PROFILE_LIMITS = {"about": 139, "address": 256, "description": 512, "email": 128}
PROFILE_VERTICALS = (
    "UNDEFINED",
    "OTHER",
    "AUTO",
    "BEAUTY",
    "APPAREL",
    "EDU",
    "ENTERTAIN",
    "EVENT_PLAN",
    "FINANCE",
    "GROCERY",
    "GOVT",
    "HOTEL",
    "HEALTH",
    "NONPROFIT",
    "PROF_SERVICES",
    "RETAIL",
    "TRAVEL",
    "RESTAURANT",
)
_PHOTO_TYPES = ("image/jpeg", "image/png")
_PHOTO_MAX_BYTES = 5 * 1024 * 1024
_QR_MESSAGE_MAX = 140


def _phone_number_id(channel: WhatsappChannel) -> str:
    _waba(channel)  # 422 unless it's a connected Cloud channel
    cfg = channel.provider_config if isinstance(channel.provider_config, dict) else {}
    pnid = cfg.get("phone_number_id")
    if not pnid:
        raise _unprocessable("La bandeja no tiene el identificador del número de Meta.")
    return str(pnid)


# ---------------------------------------------------------------------------
# The number's state
# ---------------------------------------------------------------------------
async def phone_status(channel: WhatsappChannel) -> dict[str, Any]:
    """Name, quality, limits and connection state of the number on Meta."""
    pnid = _phone_number_id(channel)
    data = await _graph_call(channel, "GET", pnid, params={"fields": _PHONE_FIELDS})
    for field in _LIMIT_FIELDS:
        try:
            extra = await _graph_call(channel, "GET", pnid, params={"fields": field})
        except ChatwootHTTPException:
            continue
        if extra.get(field) is not None:
            data[field] = extra[field]
    throughput = data.get("throughput")
    limit = data.get("whatsapp_business_manager_messaging_limit") or data.get(
        "messaging_limit_tier"
    )
    return {
        "phone_number": channel.phone_number,
        "display_phone_number": data.get("display_phone_number"),
        "verified_name": data.get("verified_name"),
        "name_status": data.get("name_status"),
        "quality_rating": data.get("quality_rating"),
        "messaging_limit": limit,
        "status": data.get("status"),
        "code_verification_status": data.get("code_verification_status"),
        "throughput": throughput.get("level") if isinstance(throughput, dict) else None,
        "platform_type": data.get("platform_type"),
    }


# ---------------------------------------------------------------------------
# Business profile
# ---------------------------------------------------------------------------
async def get_profile(channel: WhatsappChannel) -> dict[str, Any]:
    pnid = _phone_number_id(channel)
    body = await _graph_call(
        channel,
        "GET",
        f"{pnid}/whatsapp_business_profile",
        params={"fields": ",".join((*PROFILE_FIELDS, "profile_picture_url"))},
    )
    rows = body.get("data")
    profile = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
    return {
        **{field: profile.get(field) for field in PROFILE_FIELDS},
        "websites": list(profile.get("websites") or []),
        "profile_picture_url": profile.get("profile_picture_url"),
    }


def _clean_profile(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field, limit in _PROFILE_LIMITS.items():
        if field in payload and payload[field] is not None:
            value = str(payload[field]).strip()
            if len(value) > limit:
                raise _unprocessable(f"{field} admite hasta {limit} caracteres.")
            out[field] = value
    if "websites" in payload and payload["websites"] is not None:
        sites = [str(s).strip() for s in payload["websites"] if str(s).strip()]
        if len(sites) > 2:
            raise _unprocessable("Se pueden poner hasta 2 sitios web.")
        for site in sites:
            if not site.startswith(("http://", "https://")) or len(site) > 256:
                raise _unprocessable("Cada sitio web empieza con http:// o https://.")
        out["websites"] = sites
    if payload.get("vertical"):
        vertical = str(payload["vertical"]).upper()
        if vertical not in PROFILE_VERTICALS:
            raise _unprocessable("Rubro desconocido.")
        out["vertical"] = vertical
    return out


async def update_profile(channel: WhatsappChannel, payload: dict[str, Any]) -> dict[str, Any]:
    pnid = _phone_number_id(channel)
    fields = _clean_profile(payload)
    if fields:
        await _graph_call(
            channel,
            "POST",
            f"{pnid}/whatsapp_business_profile",
            json={"messaging_product": "whatsapp", **fields},
        )
    return await get_profile(channel)


async def update_profile_photo(
    channel: WhatsappChannel, *, content: bytes, content_type: str
) -> dict[str, Any]:
    """Meta takes the photo through its resumable upload (an upload session
    on the app, then the bytes) and a handle on the profile."""
    pnid = _phone_number_id(channel)
    if content_type not in _PHOTO_TYPES:
        raise _unprocessable("La foto tiene que ser JPG o PNG.")
    if not content or len(content) > _PHOTO_MAX_BYTES:
        raise _unprocessable("La foto pesa hasta 5 MB.")
    settings = get_settings()
    if not settings.meta_app_id:
        raise _unprocessable("Falta META_APP_ID en Ajustes → Instalación.")
    _, token = _waba(channel)
    base = f"{_cloud_api_base()}/{settings.meta_graph_api_version}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            session_resp = await client.post(
                f"{base}/{settings.meta_app_id}/uploads",
                params={"file_length": len(content), "file_type": content_type},
                headers={"Authorization": f"Bearer {token}"},
            )
            upload_id = session_resp.json().get("id") if session_resp.is_success else None
            if not upload_id:
                log.warning(
                    "whatsapp.profile.photo_session_failed channel_id=%s status=%s body=%s",
                    channel.id,
                    session_resp.status_code,
                    session_resp.text[:300],
                )
                raise _unprocessable("Meta no aceptó la foto. Probá con otra.")
            upload_resp = await client.post(
                f"{base}/{upload_id}",
                content=content,
                headers={"Authorization": f"OAuth {token}", "file_offset": "0"},
            )
            handle = upload_resp.json().get("h") if upload_resp.is_success else None
    except httpx.HTTPError as exc:
        raise _unprocessable("Meta no respondió. Probá de nuevo en un rato.") from exc
    if not handle:
        raise _unprocessable("Meta no aceptó la foto. Probá con otra.")
    await _graph_call(
        channel,
        "POST",
        f"{pnid}/whatsapp_business_profile",
        json={"messaging_product": "whatsapp", "profile_picture_handle": handle},
    )
    return await get_profile(channel)


# ---------------------------------------------------------------------------
# QR codes and short links (Meta keeps them and counts nothing for us)
# ---------------------------------------------------------------------------
_QR_FIELDS = "code,prefilled_message,deep_link_url,qr_image_url.format(PNG)"


def _present_qr(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": row.get("code"),
        "prefilled_message": row.get("prefilled_message"),
        "deep_link_url": row.get("deep_link_url"),
        "qr_image_url": row.get("qr_image_url"),
    }


async def list_qr_codes(channel: WhatsappChannel) -> list[dict[str, Any]]:
    pnid = _phone_number_id(channel)
    body = await _graph_call(
        channel, "GET", f"{pnid}/message_qrdls", params={"fields": _QR_FIELDS}
    )
    rows = body.get("data")
    return [_present_qr(r) for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


async def save_qr_code(
    channel: WhatsappChannel, *, message: str, code: str | None = None
) -> list[dict[str, Any]]:
    """Create a QR (or change its message when ``code`` is given)."""
    pnid = _phone_number_id(channel)
    text = (message or "").strip()
    if not text:
        raise _unprocessable("Escribí el mensaje con el que empieza el chat.")
    if len(text) > _QR_MESSAGE_MAX:
        raise _unprocessable(f"El mensaje admite hasta {_QR_MESSAGE_MAX} caracteres.")
    params: dict[str, Any] = {"prefilled_message": text, "generate_qr_image": "PNG"}
    if code:
        params["code"] = code
    await _graph_call(channel, "POST", f"{pnid}/message_qrdls", params=params)
    return await list_qr_codes(channel)


async def delete_qr_code(channel: WhatsappChannel, *, code: str) -> list[dict[str, Any]]:
    pnid = _phone_number_id(channel)
    await _graph_call(channel, "DELETE", f"{pnid}/message_qrdls/{code}")
    return await list_qr_codes(channel)


__all__ = [
    "PROFILE_VERTICALS",
    "delete_qr_code",
    "get_profile",
    "list_qr_codes",
    "phone_status",
    "save_qr_code",
    "update_profile",
    "update_profile_photo",
]
