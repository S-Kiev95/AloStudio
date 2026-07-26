"""Integration hooks CRUD service.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/integrations/hooks_controller.rb
  reference/chatwoot/app/models/integrations/hook.rb (validators)
"""

from __future__ import annotations

import secrets
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.integrations.models import (
    HOOK_STATUS_DISABLED,
    HOOK_STATUS_ENABLED,
    HOOK_TYPE_ACCOUNT,
    HOOK_TYPE_INBOX,
    IntegrationsHook,
    find_app,
    hook_type_from_str,
)


def _new_token() -> str:
    """Mirror Rails' ``has_secure_token`` — 24-char URL-safe random."""
    return secrets.token_urlsafe(18)[:24]


def _validate_app(app_id: Any) -> str:
    if not isinstance(app_id, str) or not app_id.strip():
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "App can't be blank"},
        )
    if find_app(app_id) is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"App {app_id!r} not supported"},
        )
    return app_id


async def _ensure_unique_app(
    session: AsyncSession, *, account_id: int, app_id: str
) -> None:
    """Mirror ``validates :app_id, uniqueness: { scope: :account_id }``.

    Apps with ``allow_multiple_hooks=True`` (e.g. ``webhook``) can have
    many rows per account; others enforce one-per-account."""
    app = find_app(app_id)
    if app is None or app.allow_multiple_hooks:
        return
    existing = (
        await session.exec(
            select(IntegrationsHook).where(
                IntegrationsHook.account_id == account_id,
                IntegrationsHook.app_id == app_id,
            )
        )
    ).first()
    if existing is not None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "App has already been taken"},
        )


async def list_hooks(
    session: AsyncSession, *, account_id: int
) -> list[IntegrationsHook]:
    return list(
        (
            await session.exec(
                select(IntegrationsHook)
                .where(IntegrationsHook.account_id == account_id)
                .order_by(IntegrationsHook.id.asc())
            )
        ).all()
    )


async def fetch_hook(
    session: AsyncSession, *, account_id: int, hook_id: int
) -> IntegrationsHook | None:
    return (
        await session.exec(
            select(IntegrationsHook).where(
                IntegrationsHook.id == hook_id,
                IntegrationsHook.account_id == account_id,
            )
        )
    ).first()


async def create_hook(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> IntegrationsHook:
    app_id = _validate_app(payload.get("app_id"))
    inbox_id = payload.get("inbox_id")
    hook_type_raw = payload.get("hook_type")
    if hook_type_raw is None:
        hook_type = (
            HOOK_TYPE_INBOX if inbox_id is not None else HOOK_TYPE_ACCOUNT
        )
    else:
        hook_type = hook_type_from_str(hook_type_raw)

    if hook_type == HOOK_TYPE_INBOX and inbox_id is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Inbox is required for inbox hooks"},
        )

    await _ensure_unique_app(session, account_id=account_id, app_id=app_id)

    hook = IntegrationsHook(
        account_id=account_id,
        inbox_id=inbox_id,
        app_id=app_id,
        hook_type=hook_type,
        status=HOOK_STATUS_ENABLED,
        settings=payload.get("settings") or {},
        access_token=_new_token(),
    )
    session.add(hook)
    await session.flush()
    await session.refresh(hook)
    return hook


async def update_hook(
    session: AsyncSession,
    *,
    hook: IntegrationsHook,
    payload: dict[str, Any],
) -> IntegrationsHook:
    """Mirror Rails ``update!(permitted_params.slice(:status, :settings))``
    — only status + settings are mutable post-create."""
    if "status" in payload:
        raw = payload.get("status")
        if isinstance(raw, bool):
            hook.status = HOOK_STATUS_ENABLED if raw else HOOK_STATUS_DISABLED
        elif raw in ("enabled", 1):
            hook.status = HOOK_STATUS_ENABLED
        elif raw in ("disabled", 0):
            hook.status = HOOK_STATUS_DISABLED
        else:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "Status is invalid"},
            )
    if "settings" in payload:
        settings = payload.get("settings")
        if settings is not None and not isinstance(settings, dict):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "Settings must be an object"},
            )
        hook.settings = settings or {}
    session.add(hook)
    await session.flush()
    await session.refresh(hook)
    return hook


async def destroy_hook(
    session: AsyncSession, *, hook: IntegrationsHook
) -> None:
    await session.delete(hook)
    await session.flush()


__all__ = [
    "create_hook",
    "destroy_hook",
    "fetch_hook",
    "list_hooks",
    "update_hook",
]
