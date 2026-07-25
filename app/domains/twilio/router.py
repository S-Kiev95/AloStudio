"""Twilio webhook surface — ``POST /twilio/callback``.

Twilio's webhook payload arrives as
``application/x-www-form-urlencoded`` (or ``multipart/form-data``
when MMS media is attached). FastAPI's ``Request.form()`` handles
both, returning a flat ``FormData`` we coerce to a dict before
passing to the processor.

Anchors:
  reference/chatwoot/app/controllers/twilio/callback_controller.rb
  reference/chatwoot/config/routes.rb (namespace :twilio
    -> resources :callback, only: [:create])

The endpoint always 200s — Rails returns ``head :no_content``
(204), but Twilio accepts any 2xx and we shape the response as
``{}`` so the wire body is well-formed JSON for tooling that
inspects it. Twilio retries on 5xx so we want to break the retry
loop on every malformed / unknown payload.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.core.twilio_signature import verify_twilio_signature

router = APIRouter(
    tags=["twilio-webhooks"],
)


def _external_url(request: Request) -> str:
    """Reconstruct the URL Twilio signed.

    Twilio computes the signature over the exact public URL it POSTed
    to, so behind a reverse proxy we must honour ``X-Forwarded-Proto`` /
    ``X-Forwarded-Host`` rather than the internal scheme/host the app
    sees. Includes the query string when present.
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"
    return f"{proto}://{host}{path}"


@router.post("/twilio/callback")
async def twilio_receive(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Receive a Twilio SMS webhook.

    Always returns 200 on success — see module docstring. When
    ``twilio_verify_signature`` is on, an invalid/absent
    ``X-Twilio-Signature`` (or an unresolvable channel) 403s instead.
    """
    try:
        form = await request.form()
    except Exception:  # noqa: BLE001
        return {}

    params: dict[str, Any] = {key: form[key] for key in form}

    from app.domains.twilio.incoming import (
        _resolve_channel,
        process_twilio_webhook,
    )

    # Per-POST signature gate (CH-1). Opt-in via
    # ``twilio_verify_signature`` (default OFF in code / ON in
    # .env.example). Resolve the channel first for its ``auth_token``,
    # then verify HMAC-SHA1 over the external URL + sorted params. Fails
    # closed (403) when the channel can't be resolved or the signature
    # doesn't match.
    if get_settings().twilio_verify_signature:
        resolved = await _resolve_channel(session, params=params)
        auth_token = resolved[0].auth_token if resolved else None
        if not verify_twilio_signature(
            auth_token,
            _external_url(request),
            params,
            request.headers.get("X-Twilio-Signature"),
        ):
            raise ChatwootHTTPException(
                status_code=403,
                detail={"error": "Invalid signature"},
            )

    try:
        await process_twilio_webhook(session, params=params)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "twilio.webhook.process_failed"
        )

    return {}


__all__ = ["router"]
