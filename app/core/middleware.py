"""Request-id middleware — Rails' ``ActionDispatch::RequestId`` port.

Reads ``X-Request-Id`` from the incoming request (mint a new UUID if
missing), echoes it back on the response, and binds it onto the
structured-log contextvar so every log line emitted during the
request carries the same id.

Ported from:
  reference/chatwoot/config/application.rb
    (config.action_dispatch.request_id is implicit in Rails)

Usage::

    app.add_middleware(RequestIdMiddleware)

Pairs with :mod:`app.core.logging`'s
``structlog.contextvars.merge_contextvars`` processor so the
``request_id`` field appears on every line without manual binding.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

HEADER_NAME = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Per-request request_id binding."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        incoming = request.headers.get(HEADER_NAME)
        # Accept caller-supplied id when present + sane; otherwise mint.
        if incoming and 1 <= len(incoming) <= 255:
            request_id = incoming
        else:
            request_id = str(uuid.uuid4())

        # Bind onto the structlog context for the duration of the
        # request — the ``merge_contextvars`` processor in
        # :mod:`app.core.logging` picks this up and decorates every
        # log entry with it.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            # Echo back regardless of success/failure.
            structlog.contextvars.clear_contextvars()
        response.headers[HEADER_NAME] = request_id
        return response


__all__ = ["HEADER_NAME", "RequestIdMiddleware"]
