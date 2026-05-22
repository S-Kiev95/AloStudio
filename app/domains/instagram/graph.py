"""Per-channel Graph API host selection (I.10d).

Facebook Login publishes via ``graph.facebook.com``; Instagram Login via
``graph.instagram.com``. Rather than thread a base URL through every
client call, the service sets a task-local host for the duration of an
operation and the clients read it via :func:`graph_base`.

The default is ``graph.facebook.com`` so every existing call site (and
every channel without an explicit ``login_type``) behaves exactly as
before — Instagram Login is strictly additive.

ContextVars are task-local: FastAPI runs each request in its own task,
and the worker runs each job in its own task, so concurrent operations
never clobber each other's host.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar

from app.core.config import get_settings

_DEFAULT_HOST = "graph.facebook.com"
_INSTAGRAM_HOST = "graph.instagram.com"

_host_var: ContextVar[str | None] = ContextVar(
    "ig_graph_host", default=None
)


def host_for_login_type(login_type: str | None) -> str:
    """``graph.instagram.com`` for Instagram Login, else the default
    Facebook host (covers ``facebook`` + legacy/None channels)."""
    return _INSTAGRAM_HOST if login_type == "instagram" else _DEFAULT_HOST


def graph_base() -> str:
    """The Graph API base URL for the current task's host."""
    host = _host_var.get() or _DEFAULT_HOST
    return f"https://{host}/{get_settings().meta_graph_api_version}"


@contextlib.contextmanager
def graph_host(host: str | None) -> Iterator[None]:
    """Set the Graph host for the duration of the block, then restore."""
    token = _host_var.set(host)
    try:
        yield
    finally:
        _host_var.reset(token)


__all__ = ["graph_base", "graph_host", "host_for_login_type"]
