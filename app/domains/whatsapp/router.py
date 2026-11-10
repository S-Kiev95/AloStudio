"""WhatsApp webhook surface — ``/webhooks/whatsapp/{phone_number}``.

Two endpoints share the path:

  * ``GET`` — Meta's verification handshake. Echoes back
    ``hub.challenge`` when ``hub.verify_token`` matches the channel's
    stored ``webhook_verify_token``. 401 with the error envelope
    otherwise. Mirrors Rails' ``MetaTokenVerifyConcern``.

  * ``POST`` — receives inbound message payloads from Meta (Cloud) or
    360dialog. Phase 5c.2 just acknowledges the payload (and returns
    200 so Meta doesn't retry); the actual ingest happens in 5c.3
    via ``process_cloud_webhook``.

Anchors:
  reference/chatwoot/app/controllers/webhooks/whatsapp_controller.rb
  reference/chatwoot/app/controllers/concerns/meta_token_verify_concern.rb
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import PlainTextResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.core.meta_signature import verify_sha256_signature
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    Inbox,
    WhatsappChannel,
)

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks/whatsapp",
    tags=["whatsapp-webhooks"],
)


async def _resolve_channel(
    session: AsyncSession, *, phone_number: str
) -> tuple[WhatsappChannel, Inbox]:
    """Load the WhatsappChannel + Inbox by phone_number.

    Raises 404 with ``{"error": "Phone number not found"}`` when no
    channel matches — Rails uses ``ActiveRecord::RecordNotFound`` here
    which ActionController auto-renders as 404.
    """
    channel = (
        await session.exec(
            select(WhatsappChannel).where(
                WhatsappChannel.phone_number == phone_number
            )
        )
    ).first()
    if channel is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Phone number not found"},
        )
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_WHATSAPP,
                Inbox.channel_id == channel.id,
            )
        )
    ).first()
    if inbox is None:
        # Defensive: orphaned channel row -> same 404 as missing channel.
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Phone number not found"},
        )
    return channel, inbox


@router.get("/{phone_number}")
async def whatsapp_verify(
    phone_number: Annotated[str, Path()],
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
    hub_verify_token: Annotated[
        str | None, Query(alias="hub.verify_token")
    ] = None,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Meta verification handshake.

    Mirrors Rails' ``MetaTokenVerifyConcern#verify``:
      * Look up the channel by phone_number.
      * Compute the expected token from ``provider_config
        ['webhook_verify_token']`` (None if channel missing).
      * Token matches -> echo back ``hub.challenge``.
      * Anything else (no channel, missing token, mismatch) -> 401
        with the canonical error envelope. Unknown phones get the
        same 401 as wrong tokens — matches Rails' ``valid_token?``
        which short-circuits to nil + falls through to the 401 branch.
    """
    expected = await _expected_verify_token(
        session, phone_number=phone_number
    )
    if (
        hub_verify_token is None
        or expected is None
        or hub_verify_token != expected
    ):
        raise ChatwootHTTPException(
            status_code=401,
            detail={"error": "Error; wrong verify token"},
        )
    # Meta requires the challenge echoed back as raw text — the default
    # JSONResponse would wrap it in quotes (``"123"``) with an
    # application/json content-type, which Meta rejects. PlainTextResponse
    # returns the bare value.
    return PlainTextResponse(hub_challenge or "")


@router.post("/{phone_number}")
async def whatsapp_receive(
    phone_number: Annotated[str, Path()],
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Receive a WhatsApp webhook payload.

    Always 200 — Rails' ``WhatsappController#process_payload`` doesn't
    check whether the phone resolves before queuing the job, so an
    unknown number gets the same ``head :ok`` as a known one. Meta
    retries on 5xx; we never want to send 5xx for a malformed body
    we can't parse either.

    Unknown phones drop the payload silently (no Message rows). Known
    phones run the per-provider processor (5c.3 implements the cloud
    branch).
    """
    raw = await request.body()

    # Per-POST signature gate (CH-1). Opt-in via
    # ``meta_verify_webhook_signature`` (default OFF for backward-compat,
    # ON in .env.example). The GET hub.verify_token handshake only gates
    # subscription setup; this rejects forged inbound WhatsApp payloads.
    # Fails closed when the secret is unset. WhatsApp Cloud signs with
    # the Meta app secret, same as Instagram/Messenger.
    if not _signature_ok(raw, request):
        raise ChatwootHTTPException(
            status_code=401,
            detail={"error": "Invalid signature"},
        )

    try:
        payload = json.loads(raw)
    except Exception:  # noqa: BLE001
        return {"status": "ok"}

    channel_inbox = await _resolve_channel_optional(
        session, phone_number=phone_number
    )
    if channel_inbox is None:
        return {"status": "ok"}
    channel, inbox = channel_inbox

    await _process(session, channel=channel, inbox=inbox, payload=payload)
    return {"status": "ok"}


async def _process(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    payload: dict[str, Any],
) -> None:
    """Run the per-provider processor; a failure is logged, never raised
    (Meta retries on 5xx and the payload would fail the same way)."""
    from app.domains.inboxes.models import (
        WHATSAPP_PROVIDER_360DIALOG,
        WHATSAPP_PROVIDER_CLOUD,
    )
    from app.domains.whatsapp.incoming_cloud import (
        process_360dialog_webhook,
        process_cloud_webhook,
    )

    try:
        if channel.provider == WHATSAPP_PROVIDER_CLOUD:
            await process_cloud_webhook(
                session, channel=channel, inbox=inbox, payload=payload
            )
        elif channel.provider == WHATSAPP_PROVIDER_360DIALOG:
            await process_360dialog_webhook(
                session, channel=channel, inbox=inbox, payload=payload
            )
    except Exception:
        log.exception("whatsapp.webhook.process_failed channel_id=%s", channel.id)


def _signature_ok(raw: bytes, request: Request) -> bool:
    """X-Hub-Signature-256 against the Meta app secret, when the
    installation verifies webhook signatures (CH-1)."""
    settings = get_settings()
    if not settings.meta_verify_webhook_signature:
        return True
    return verify_sha256_signature(
        raw,
        request.headers.get("X-Hub-Signature-256"),
        settings.meta_app_secret,
    )


# ---------------------------------------------------------------------------
# App-level webhook (F2 multitenant)
# ---------------------------------------------------------------------------
# With one Meta app for every client, Embedded Signup points each WABA here
# and Meta batches the changes of many numbers, from many accounts, in one
# POST. Each change is routed by the phone_number_id it names.
@router.get("")
async def whatsapp_app_verify(
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
    hub_verify_token: Annotated[
        str | None, Query(alias="hub.verify_token")
    ] = None,
) -> Any:
    """Meta's handshake for the app-level route: the installation's
    WHATSAPP_VERIFY_TOKEN. Unset refuses every request."""
    expected = get_settings().whatsapp_verify_token
    if not expected or hub_verify_token != expected:
        raise ChatwootHTTPException(
            status_code=401,
            detail={"error": "Error; wrong verify token"},
        )
    return PlainTextResponse(hub_challenge or "")


@router.post("")
async def whatsapp_app_receive(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Receive a batched app-level payload. Always 200, like the
    per-number route; numbers no account has connected are dropped."""
    raw = await request.body()
    if not _signature_ok(raw, request):
        raise ChatwootHTTPException(
            status_code=401,
            detail={"error": "Invalid signature"},
        )
    try:
        payload = json.loads(raw)
    except ValueError:
        return {"status": "ok"}
    if not isinstance(payload, dict):
        return {"status": "ok"}

    from app.domains.whatsapp.incoming_cloud import payloads_by_number

    for number_id, part in payloads_by_number(payload).items():
        resolved = await _resolve_by_number_id(session, phone_number_id=number_id)
        if resolved is None:
            log.info(
                "whatsapp.app_webhook.unknown_number phone_number_id=%s", number_id
            )
            continue
        channel, inbox = resolved
        await _process(session, channel=channel, inbox=inbox, payload=part)
    return {"status": "ok"}


async def _resolve_by_number_id(
    session: AsyncSession, *, phone_number_id: str
) -> tuple[WhatsappChannel, Inbox] | None:
    """The Cloud channel whose provider_config.phone_number_id matches.

    More than one match means two accounts claim the number: nothing is
    delivered rather than guessing (Embedded Signup refuses that case).
    """
    from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD

    table = WhatsappChannel.__table__  # type: ignore[attr-defined]
    channels = list(
        (
            await session.exec(
                select(WhatsappChannel).where(
                    WhatsappChannel.provider == WHATSAPP_PROVIDER_CLOUD,
                    table.c.provider_config["phone_number_id"].astext
                    == phone_number_id,
                )
            )
        ).all()
    )
    if len(channels) != 1:
        if channels:
            log.error(
                "whatsapp.app_webhook.ambiguous_number phone_number_id=%s channels=%s",
                phone_number_id,
                [c.id for c in channels],
            )
        return None
    channel = channels[0]
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_WHATSAPP,
                Inbox.channel_id == channel.id,
            )
        )
    ).first()
    if inbox is None:
        return None
    return channel, inbox


async def _expected_verify_token(
    session: AsyncSession, *, phone_number: str
) -> str | None:
    """Mirror Rails' ``valid_token?`` token-lookup half.

    Returns ``None`` for unknown phone, missing channel, or missing
    token — the caller treats any of these as "verification fails"
    and renders 401.
    """
    channel = (
        await session.exec(
            select(WhatsappChannel).where(
                WhatsappChannel.phone_number == phone_number
            )
        )
    ).first()
    if channel is None:
        return None
    return channel.webhook_verify_token


async def _resolve_channel_optional(
    session: AsyncSession, *, phone_number: str
) -> tuple[WhatsappChannel, Inbox] | None:
    """Same as :func:`_resolve_channel` but returns None instead of
    raising. Used by the POST receive endpoint where unknown phones
    drop silently."""
    channel = (
        await session.exec(
            select(WhatsappChannel).where(
                WhatsappChannel.phone_number == phone_number
            )
        )
    ).first()
    if channel is None:
        return None
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_WHATSAPP,
                Inbox.channel_id == channel.id,
            )
        )
    ).first()
    if inbox is None:
        return None
    return channel, inbox


__all__ = ["router"]
