"""WhatsApp Embedded Signup: a client connects its own number (F2).

The browser opens Meta's onboarding popup (JS SDK ``FB.login`` with the
installation's "Facebook Login for Business" configuration). Meta hands
back an authorization ``code``, and the popup's message event names the
WhatsApp Business Account (``waba_id``) and ``phone_number_id`` the
client picked. Server side, in this order:

1. Exchange the code for a business token (app id + secret).
2. ``debug_token``: the token must belong to our app and carry
   ``whatsapp_business_management`` on that WABA. This is what proves the
   number is the client's: the ids come from Meta, not from a form.
3. Read the number from the WABA (display number, verified name).
4. Subscribe our app to the WABA, pointing its webhooks at the app-level
   route (``/webhooks/whatsapp``), which routes by ``phone_number_id``.
5. Save the channel: a new inbox, or a fresh token for the same account's
   existing one. A number connected in another account is refused.
6. Register the number on the Cloud API when Meta says it still needs it
   (best effort; a failure is logged).

Nothing is saved before step 4 succeeds, so a failed connection leaves no
half-made inbox behind.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

import httpx
from sqlalchemy import or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.domains.accounts.models import Account
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    WHATSAPP_PROVIDER_CLOUD,
    Inbox,
    WhatsappChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.whatsapp.cloud_provider import _api_base

log = logging.getLogger(__name__)

_TIMEOUT = 20.0
_WABA_SCOPE = "whatsapp_business_management"


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


def _graph(path: str) -> str:
    version = get_settings().meta_graph_api_version
    return f"{_api_base()}/{version}/{path.lstrip('/')}"


def signup_info() -> dict[str, Any]:
    """What the "Conectar WhatsApp" button needs, and what is missing."""
    settings = get_settings()
    named = (
        ("META_APP_ID", settings.meta_app_id),
        ("META_APP_SECRET", settings.meta_app_secret),
        ("WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID", settings.whatsapp_embedded_signup_config_id),
        ("WHATSAPP_VERIFY_TOKEN", settings.whatsapp_verify_token),
    )
    missing = [name for name, value in named if not value]
    return {
        "ready": not missing,
        "missing": missing,
        "app_id": settings.meta_app_id,
        "config_id": settings.whatsapp_embedded_signup_config_id,
        "graph_api_version": settings.meta_graph_api_version,
    }


async def _call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    failure: str,
    params: dict[str, Any] | None = None,
    token: str | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    try:
        resp = await client.request(method, _graph(path), params=params, headers=headers, json=json)
    except httpx.HTTPError as exc:
        log.warning("whatsapp.embedded_signup.transport path=%s err=%s", path, exc)
        raise _unprocessable(f"{failure}: Meta no respondió. Probá de nuevo.") from exc
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code >= 400 or not isinstance(body, dict):
        error = body.get("error") if isinstance(body, dict) else None
        detail = error.get("message") if isinstance(error, dict) else None
        log.warning(
            "whatsapp.embedded_signup.api_error path=%s status=%s body=%s",
            path,
            resp.status_code,
            resp.text[:300],
        )
        raise _unprocessable(f"{failure}: {detail or 'Meta rechazó el pedido.'}")
    return body


async def _exchange_code(client: httpx.AsyncClient, code: str) -> str:
    settings = get_settings()
    body = await _call(
        client,
        "GET",
        "oauth/access_token",
        failure="No se pudo validar la autorización de Meta",
        params={
            "client_id": settings.meta_app_id,
            "client_secret": settings.meta_app_secret,
            "code": code,
        },
    )
    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        raise _unprocessable("Meta no devolvió un token. Probá conectar de nuevo.")
    return token


async def _check_token_reaches_waba(client: httpx.AsyncClient, token: str, waba_id: str) -> None:
    """The token is ours and was granted on this WABA."""
    settings = get_settings()
    body = await _call(
        client,
        "GET",
        "debug_token",
        failure="No se pudo comprobar el permiso de Meta",
        params={
            "input_token": token,
            "access_token": f"{settings.meta_app_id}|{settings.meta_app_secret}",
        },
    )
    raw = body.get("data")
    data: dict[str, Any] = raw if isinstance(raw, dict) else {}
    if not data.get("is_valid") or str(data.get("app_id")) != str(settings.meta_app_id):
        raise _unprocessable("La autorización de Meta no es válida para AloStudio.")
    for grant in data.get("granular_scopes") or []:
        if not isinstance(grant, dict) or grant.get("scope") != _WABA_SCOPE:
            continue
        targets = grant.get("target_ids")
        # No target list means the scope covers every object the user chose.
        if not targets or waba_id in {str(t) for t in targets}:
            return
    raise _unprocessable(
        "La autorización no incluye esa cuenta de WhatsApp Business. "
        "Volvé a conectar y elegila en la ventana de Meta."
    )


async def _phone_info(
    client: httpx.AsyncClient, token: str, waba_id: str, phone_number_id: str
) -> dict[str, Any]:
    body = await _call(
        client,
        "GET",
        f"{waba_id}/phone_numbers",
        failure="No se pudieron leer los números de la cuenta",
        token=token,
        params={
            "fields": "id,display_phone_number,verified_name,"
            "code_verification_status,platform_type",
        },
    )
    for phone in body.get("data") or []:
        if isinstance(phone, dict) and str(phone.get("id")) == phone_number_id:
            digits = "".join(
                ch for ch in str(phone.get("display_phone_number") or "") if ch.isdigit()
            )
            if not digits:
                break
            return {
                "phone_number_id": phone_number_id,
                "phone_number": f"+{digits}",
                "verified_name": phone.get("verified_name") or f"+{digits}",
                "needs_registration": (
                    phone.get("code_verification_status") != "VERIFIED"
                    or phone.get("platform_type") == "NOT_APPLICABLE"
                ),
            }
    raise _unprocessable("Ese número no está en la cuenta de WhatsApp Business elegida.")


async def _subscribe_waba(client: httpx.AsyncClient, token: str, waba_id: str) -> None:
    """Subscribe our app to the WABA, then point its webhooks at the
    app-level route. Meta needs the plain subscription before the override."""
    settings = get_settings()
    await _call(
        client,
        "POST",
        f"{waba_id}/subscribed_apps",
        failure="No se pudo suscribir AloStudio a la cuenta de WhatsApp",
        token=token,
    )
    await _call(
        client,
        "POST",
        f"{waba_id}/subscribed_apps",
        failure="No se pudo registrar el webhook de WhatsApp",
        token=token,
        json={
            "override_callback_uri": (f"{settings.app_base_url.rstrip('/')}/webhooks/whatsapp"),
            "verify_token": settings.whatsapp_verify_token,
        },
    )


async def _register_number(client: httpx.AsyncClient, token: str, channel: WhatsappChannel) -> None:
    """Best effort: a number fresh from the popup must be registered on
    the Cloud API before it can send. The PIN is the number's two-step
    verification PIN, kept for later re-registrations."""
    config = dict(channel.provider_config or {})
    pin = str(config.get("verification_pin") or f"{secrets.randbelow(900_000) + 100_000}")
    try:
        await _call(
            client,
            "POST",
            f"{config.get('phone_number_id')}/register",
            failure="No se pudo registrar el número",
            token=token,
            json={"messaging_product": "whatsapp", "pin": pin},
        )
    except ChatwootHTTPException:
        log.warning("whatsapp.embedded_signup.register_failed channel_id=%s", channel.id)
        return
    config["verification_pin"] = pin
    channel.provider_config = config


async def _existing_channel(
    session: AsyncSession, *, phone_number: str, phone_number_id: str
) -> WhatsappChannel | None:
    table = WhatsappChannel.__table__  # type: ignore[attr-defined]
    return (
        await session.exec(
            select(WhatsappChannel).where(
                or_(
                    col(WhatsappChannel.phone_number) == phone_number,
                    table.c.provider_config["phone_number_id"].astext == phone_number_id,
                )
            )
        )
    ).first()


async def connect_number(
    session: AsyncSession,
    *,
    account: Account,
    code: str,
    waba_id: str,
    phone_number_id: str,
) -> tuple[Inbox, WhatsappChannel, bool]:
    """Connect (or reconnect) a number → ``(inbox, channel, created)``."""
    info = signup_info()
    if not info["ready"]:
        raise _unprocessable(
            "Falta configurar WhatsApp Embedded Signup: "
            f"{', '.join(info['missing'])}. Cargalos en Ajustes → Instalación."
        )
    if not (code and waba_id and phone_number_id):
        raise _unprocessable("Faltan datos de la ventana de Meta. Probá conectar de nuevo.")
    assert account.id is not None

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        token = await _exchange_code(client, code)
        await _check_token_reaches_waba(client, token, waba_id)
        phone = await _phone_info(client, token, waba_id, phone_number_id)

        existing = await _existing_channel(
            session,
            phone_number=phone["phone_number"],
            phone_number_id=phone_number_id,
        )
        if existing is not None and existing.account_id != account.id:
            raise _unprocessable(
                "Ese número ya está conectado en otra cuenta de AloStudio. "
                "Desconectalo de allí primero."
            )

        await _subscribe_waba(client, token, waba_id)

        provider_config = {
            **((existing.provider_config or {}) if existing is not None else {}),
            "api_key": token,
            "phone_number_id": phone_number_id,
            "business_account_id": waba_id,
            "source": "embedded_signup",
        }
        if existing is None:
            result = await InboxBuilder(
                session,
                InboxBuilderParams(
                    account=account,
                    name=str(phone["verified_name"]),
                    channel_type="whatsapp",
                    channel_params={
                        "phone_number": phone["phone_number"],
                        "provider": WHATSAPP_PROVIDER_CLOUD,
                        "provider_config": provider_config,
                    },
                ),
            ).perform()
            inbox, channel, created = result.inbox, result.channel, True
            assert isinstance(channel, WhatsappChannel)
        else:
            channel = existing
            channel.provider = WHATSAPP_PROVIDER_CLOUD
            channel.provider_config = provider_config
            found = (
                await session.exec(
                    select(Inbox).where(
                        Inbox.channel_type == CHANNEL_TYPE_WHATSAPP,
                        Inbox.channel_id == channel.id,
                    )
                )
            ).first()
            if found is None:
                raise _unprocessable("La bandeja de ese número no existe más.")
            inbox, created = found, False

        if phone["needs_registration"]:
            await _register_number(client, token, channel)

    session.add(channel)
    await session.flush()
    log.info(
        "whatsapp.embedded_signup.connected account_id=%s channel_id=%s created=%s",
        account.id,
        channel.id,
        created,
    )
    return inbox, channel, created


__all__ = ["connect_number", "signup_info"]
