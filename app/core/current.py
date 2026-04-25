"""ContextVar mirrors of Rails' ``Current`` attributes.

Rails uses ``ActiveSupport::CurrentAttributes`` to thread the current
user through the request cycle — ``Current.user`` is read from anywhere
in controllers, models, listeners. FastAPI has no thread-local
equivalent; we use :class:`contextvars.ContextVar`, which is naturally
scoped to the current asyncio task (parallel requests don't leak into
each other).

The :func:`app.core.deps.account_context` dependency sets
:data:`current_user_ctx` on entry, which makes the performer visible to
the :class:`~app.domains.conversations.listeners.ActionCableListener`
without plumbing ``user`` through every service-layer signature.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.domains.users.models import User

# ``None`` when the request is anonymous (widget, public endpoints). The
# ActionCableListener's ``broadcast`` checks for ``None`` before setting
# the ``performer`` key — matches Rails' ``Current.user.present?`` guard.
current_user_ctx: ContextVar["User | None"] = ContextVar("current_user", default=None)


__all__ = ["current_user_ctx"]
