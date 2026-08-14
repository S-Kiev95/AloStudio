import logging
import re
import sys
from typing import Any

import structlog

from app.core.config import get_settings

REDACTED = "[REDACTED]"

# Query-string parameters that carry a credential. Graph API calls put the
# page token in the URL, and httpx logs the whole request line at INFO — so
# an ordinary request log writes a live token to disk.
_SECRET_QS_RE = re.compile(
    r"\b(access_token|client_secret|client_token|refresh_token|api_key"
    r"|app_secret|appsecret_proof|signature)=[^&\s\"'<>]+",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"\b(Bearer\s+)[\w.\-]+", re.IGNORECASE)
# A bare Meta token, for the routes the two patterns above do not cover
# (an exception message, a dict repr, a token logged on its own).
_META_TOKEN_RE = re.compile(r"\bEAA[A-Za-z0-9]{20,}")

# Cheap gate so the common record — which holds no credential — pays a
# substring scan instead of three regex passes.
_HINTS = ("token", "secret", "bearer", "api_key", "signature", "eaa")


def _needs_scrub(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _HINTS)


def scrub_secrets(text: str) -> str:
    """Return ``text`` with any credential replaced by ``[REDACTED]``."""
    if not _needs_scrub(text):
        return text
    text = _SECRET_QS_RE.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    text = _BEARER_RE.sub(lambda m: f"{m.group(1)}{REDACTED}", text)
    return _META_TOKEN_RE.sub(REDACTED, text)


def _scrub_arg(value: Any) -> Any:
    # Numbers stay numbers — httpx formats the status code with ``%d``, so
    # handing it a string would raise inside the logging call.
    if value is None or isinstance(value, (int, float, complex)):
        return value
    try:
        text = value if isinstance(value, str) else str(value)
    except Exception:  # noqa: BLE001 - a broken __str__ must not kill logging
        return value
    scrubbed = scrub_secrets(text)
    # Substituting only when something was removed leaves every other
    # object with its own formatting behaviour.
    return scrubbed if scrubbed != text else value


class SecretRedactingFilter(logging.Filter):
    """Strips credentials from a record before any handler formats it.

    Rewrites the record rather than the formatted line so it protects every
    handler attached downstream, including ones added later.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub_secrets(record.msg)
        args = record.args
        if isinstance(args, dict):
            record.args = {k: _scrub_arg(v) for k, v in args.items()}
        elif isinstance(args, tuple) and args:
            record.args = tuple(_scrub_arg(a) for a in args)
        return True


def _add_filter_once(target: Any, redactor: logging.Filter) -> None:
    if not any(isinstance(f, SecretRedactingFilter) for f in target.filters):
        target.addFilter(redactor)


def install_secret_redaction() -> None:
    """Install the redactor for this process. Safe to call more than once.

    Attached to the HTTP loggers themselves as well as to the root handlers:
    a filter on the originating logger travels with the record no matter
    which handler ends up emitting it, which is what covers the arq worker —
    it never calls :func:`configure_logging`.
    """
    redactor = SecretRedactingFilter()
    for name in ("httpx", "httpcore", "urllib3"):
        _add_filter_once(logging.getLogger(name), redactor)
    for handler in logging.getLogger().handlers:
        _add_filter_once(handler, redactor)


def redact_processor(
    _logger: Any, _name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog counterpart of :class:`SecretRedactingFilter`.

    structlog writes through its own ``PrintLogger`` rather than stdlib
    handlers, so the logging filter never sees these records.
    """
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = scrub_secrets(value)
        elif isinstance(value, BaseException):
            # An exception's message is a common way for a request URL to
            # reach a log intact.
            event_dict[key] = scrub_secrets(str(value))
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )
    install_secret_redaction()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # After ``format_exc_info`` so the rendered traceback is scrubbed
            # too, and before the renderer, which is the last chance.
            redact_processor,
            structlog.processors.JSONRenderer()
            if settings.app_env != "local"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
