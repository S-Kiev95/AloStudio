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


async def chatwoot_http_exception_handler(
    _request: Request, exc: ChatwootHTTPException
) -> JSONResponse:
    """Emit ``exc.detail`` directly as the response body (no ``detail``
    wrapper)."""
    body = exc.detail if isinstance(exc.detail, dict | list) else {"message": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=body)
