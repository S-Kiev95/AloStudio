"""Cross-cutting HTTP error shape helpers.

The FastAPI default :class:`HTTPException` wraps its ``detail`` under a
``{"detail": ...}`` key. Every Rails controller we port here emits the body
with ``render json: {...}`` — *unwrapped*. :class:`ChatwootHTTPException`
is a marker subclass that, paired with
:func:`chatwoot_http_exception_handler` (registered in :mod:`app.main`),
delivers the body exactly as given.

This lives in ``app.core`` so any domain router can raise it without
pulling an auth-package dependency. Previously the class was defined
inside ``app.domains.auth.router``; we keep a re-export there for any
legacy imports.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class ChatwootHTTPException(HTTPException):
    """``HTTPException`` whose ``detail`` dict becomes the response body
    directly, *not* wrapped under a ``"detail"`` key.

    Why a marker subclass instead of raw :class:`JSONResponse` returns:
    every Rails controller in this port emits the body with ``render
    json: {...}`` — i.e. no envelope. FastAPI's default
    :func:`http_exception_handler` wraps ``detail`` as
    ``{"detail": ...}``. Installing a custom handler for this marker
    class lets us keep idiomatic ``raise`` flow in the controllers
    while matching Chatwoot byte-for-byte on the wire.
    """


# The English messages are the Chatwoot-compatible wording external clients
# read, so they stay as they are. Next to them goes a ``code`` the dashboard
# translates (F13): it keys on the code, never on the English text.
_CODE_BY_TEXT: dict[str, str] = {
    "Resource could not be found": "not_found",
    "You are not authorized to do this action": "not_authorized",
    "Validation failed": "validation_failed",
    "Invalid login credentials. Please try again.": "invalid_login",
    "You need to sign in or sign up before continuing.": "sign_in_required",
    "Invalid token": "invalid_token",
    "Invalid or expired SSO token.": "invalid_sso_token",
    "SSO is not enabled.": "sso_disabled",
    "El ingreso con Google no está activado.": "google_disabled",
    "No se pudo contactar a Google. Probá de nuevo.": "google_unreachable",
    "scheduled_for must be in the future": "scheduled_in_past",
    "Phone number is already taken": "phone_taken",
}
# "<Field> can't be blank" / "<Field> has already been taken": the field
# goes along so the dashboard can name it.
_CODE_BY_PATTERN: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(?P<field>[A-Z][\w ]*?) can't be blank$"), "blank"),
    (re.compile(r"^(?P<field>[A-Z][\w ]*?) has already been taken"), "taken"),
)


def _first_text(body: dict[str, Any]) -> str | None:
    for key in ("message", "error"):
        if isinstance(body.get(key), str):
            return str(body[key])
    errors = body.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], str):
        return errors[0]
    return None


def with_error_code(body: dict[str, Any]) -> dict[str, Any]:
    """``body`` plus a ``code`` (and ``field``) when its message is one the
    dashboard knows how to say in each language. Leaves a body that already
    carries a code untouched."""
    if "code" in body:
        return body
    text = _first_text(body)
    if text is None:
        return body
    if text in _CODE_BY_TEXT:
        return {**body, "code": _CODE_BY_TEXT[text]}
    for pattern, code in _CODE_BY_PATTERN:
        match = pattern.match(text)
        if match:
            field = match.group("field").strip().lower().replace(" ", "_")
            return {**body, "code": code, "field": field}
    return body


async def chatwoot_http_exception_handler(
    _request: Request, exc: ChatwootHTTPException
) -> JSONResponse:
    """Emit ``exc.detail`` directly as the response body (no ``detail``
    wrapper)."""
    body = exc.detail if isinstance(exc.detail, dict | list) else {"message": exc.detail}
    if isinstance(body, dict):
        body = with_error_code(body)
    # ``headers`` was accepted by HTTPException and silently dropped here —
    # a 429's ``Retry-After`` never reached the client.
    return JSONResponse(
        status_code=exc.status_code, content=body, headers=exc.headers
    )
