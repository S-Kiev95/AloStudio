"""Permission helpers for MCP tools.

Each tool declares its required scope (read / write / admin) via the
:func:`requires` decorator. The decorator wraps the tool body so the
scope check runs before the body — same model as Rails' Pundit
``authorize`` before_action.

It also declares two things the token scope doesn't say, for a context
that acts as a panel user (``MCPContext.user_scoped``: the agent chat, an
OAuth app): ``panel_admin`` — the panel keeps it to administrators (its
REST route uses ``require_admin``) — and ``reads`` — an ``admin`` tool that
only reads. The helpers below give such a context the panel's visibility.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.sql import Select

from app.core.errors import ChatwootHTTPException
from app.domains.conversations.models import Conversation
from app.domains.conversations.permission import (
    apply_permission_scope,
    can_view_conversation,
    can_view_inbox,
    is_administrator,
)
from app.domains.inboxes.models import Inbox, InboxMember
from app.mcp.context import current_mcp_context
from app.mcp.models import scope_satisfies

Scope = Literal["read", "write", "admin"]


class MCPPermissionError(Exception):
    """Raised when a tool is called with insufficient scope."""


def as_value_error(exc: ChatwootHTTPException) -> ValueError:
    """The service's message as a tool error (``errors`` appended)."""
    detail = exc.detail
    if not isinstance(detail, dict):
        return ValueError(str(detail))
    msg = detail.get("message") or detail.get("error") or str(detail)
    errors = detail.get("errors")
    if isinstance(errors, list) and errors:
        msg = f"{msg}: {'; '.join(str(e) for e in errors)}"
    return ValueError(str(msg))


@dataclass(frozen=True, slots=True)
class ToolPermissions:
    scope: Scope
    reads: bool
    panel_admin: bool


def requires(scope: Scope, *, reads: bool = False, panel_admin: bool = False):
    """Decorator factory — wrap a tool body to enforce ``scope``.

    ``reads``: an ``admin`` tool that changes nothing (``read`` tools
    always read). ``panel_admin``: the panel keeps it to administrators."""
    permissions = ToolPermissions(scope=scope, reads=reads or scope == "read", panel_admin=panel_admin)

    def decorator(
        fn: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = current_mcp_context()
            if not scope_satisfies(ctx.scope, scope):
                raise MCPPermissionError(
                    f"tool requires {scope!r} scope; token has {ctx.scope!r}"
                )
            if panel_admin and ctx.user_scoped and not await _acting_admin():
                raise MCPPermissionError("only an administrator of the account can use this tool")
            try:
                return await fn(*args, **kwargs)
            except ChatwootHTTPException as exc:
                # The services speak HTTP (422 + {"message": ...}); an MCP
                # client needs the message itself, not "422: {...}".
                raise as_value_error(exc) from exc

        # Read by the agent chat (which tools to offer, which to confirm).
        wrapper.permissions = permissions  # type: ignore[attr-defined]
        return wrapper

    return decorator


def permissions_of(fn: Any) -> ToolPermissions | None:
    """What a tool function declared with :func:`requires` (None without)."""
    return getattr(fn, "permissions", None)


async def _acting_admin() -> bool:
    ctx = current_mcp_context()
    if ctx.user.id is None:
        return False
    return await is_administrator(
        ctx.session, account_id=ctx.account.id, user_id=ctx.user.id  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Acting as a panel user (``MCPContext.user_scoped``): the same visibility as
# the REST API (``app.domains.conversations.permission``). A conversation or
# inbox the user can't see reads as missing, so its existence doesn't leak.
# ---------------------------------------------------------------------------
async def ensure_conversation_visible(conversation: Conversation) -> None:
    ctx = current_mcp_context()
    if not ctx.user_scoped or ctx.user.id is None:
        return
    if not await can_view_conversation(
        ctx.session,
        account_id=ctx.account.id,  # type: ignore[arg-type]
        user_id=ctx.user.id,
        conversation=conversation,
    ):
        raise ValueError(f"conversation {conversation.id} not found in this account")


async def visible_conversations(stmt: Select) -> Select:
    """Narrow a ``select(Conversation)`` to the user's inboxes."""
    ctx = current_mcp_context()
    if not ctx.user_scoped or ctx.user.id is None:
        return stmt
    return await apply_permission_scope(
        stmt,
        session=ctx.session,
        account_id=ctx.account.id,  # type: ignore[arg-type]
        current_user_id=ctx.user.id,
    )


async def ensure_inbox_visible(inbox_id: int) -> None:
    ctx = current_mcp_context()
    if not ctx.user_scoped or ctx.user.id is None:
        return
    if not await can_view_inbox(
        ctx.session,
        account_id=ctx.account.id,  # type: ignore[arg-type]
        user_id=ctx.user.id,
        inbox_id=inbox_id,
    ):
        raise ValueError(f"inbox {inbox_id} not found in this account")


async def visible_inboxes(stmt: Select) -> Select:
    """Narrow a ``select(Inbox)`` to the user's inboxes (an agent: the ones
    they are members of), like the REST inbox list."""
    ctx = current_mcp_context()
    if not ctx.user_scoped or ctx.user.id is None or await _acting_admin():
        return stmt
    return stmt.join(InboxMember, InboxMember.inbox_id == Inbox.id).where(  # type: ignore[arg-type]
        InboxMember.user_id == ctx.user.id
    )


__all__ = [
    "MCPPermissionError",
    "Scope",
    "ToolPermissions",
    "as_value_error",
    "ensure_conversation_visible",
    "ensure_inbox_visible",
    "permissions_of",
    "requires",
    "visible_conversations",
    "visible_inboxes",
]
