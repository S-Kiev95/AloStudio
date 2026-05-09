"""Macro CRUD service + execution wrapper.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/macros_controller.rb
  reference/chatwoot/app/policies/macro_policy.rb (visibility scoping)
  reference/chatwoot/app/models/macro.rb (json_actions_format validator)
  reference/chatwoot/app/services/macros/execution_service.rb (per-conv executor)
  reference/chatwoot/app/jobs/macros_execution_job.rb

Visibility rules (mirroring ``Macro.with_visibility``):
  * Index returns every ``global`` macro on the account UNION every
    ``personal`` macro authored by the calling user.
  * On create, agents are forced to ``personal`` regardless of the
    submitted visibility (Rails' ``set_visibility`` clamps it).

We expose a synchronous executor — Chatwoot's controller enqueues a
Sidekiq job (``MacrosExecutionJob``) and immediately ``head :ok``s,
but the parity surface that matters is the resulting state mutation
on the conversation. Running it inline keeps the wire shape (200 +
empty body) and avoids dragging an ARQ worker into the test path.
The async executor pattern can be lifted into a job later without
changing the API.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.automation.actions import MacroExecutor
from app.domains.conversations.models import Conversation
from app.domains.macros.models import (
    MACRO_ALLOWED_ACTIONS,
    MACRO_VISIBILITY_GLOBAL,
    MACRO_VISIBILITY_PERSONAL,
    Macro,
    macro_visibility_from_str,
)
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccountUser,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate_actions(raw: Any) -> list[dict[str, Any]]:
    """Mirror ``Macro#json_actions_format``.

    Each entry must be ``{"action_name": <str-in-allowlist>,
    "action_params": <list>}``. Rails accepts an empty array (``[]``)
    fine; only an unknown ``action_name`` raises. We allow
    ``action_params`` to be absent (defaults to ``[]``) so dashboards
    can ship actions like ``mute_conversation`` that take no args.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "actions must be an array"},
        )
    cleaned: list[dict[str, Any]] = []
    bad: list[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "each action must be an object"},
            )
        name = entry.get("action_name")
        if not isinstance(name, str) or not name:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "each action requires action_name"},
            )
        if name not in MACRO_ALLOWED_ACTIONS:
            bad.append(name)
            continue
        params = entry.get("action_params", [])
        if params is None:
            params = []
        if not isinstance(params, list):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "action_params must be an array"},
            )
        cleaned.append({"action_name": name, "action_params": params})

    if bad:
        # Match Rails' exact error string so dashboards rendering the
        # 422 body don't choke on an unfamiliar phrase.
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": f"Macro execution actions {','.join(bad)} not supported."
            },
        )
    return cleaned


# ---------------------------------------------------------------------------
# Visibility scoping
# ---------------------------------------------------------------------------
async def list_macros_for_user(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int,
) -> list[Macro]:
    """Mirror ``Macro.with_visibility(current_user, params)``.

    Visible macros = every ``global`` on the account UNION every
    ``personal`` authored by ``user_id`` on the account. Order by id
    (Rails' ``order(:id)``).
    """
    stmt = (
        select(Macro)
        .where(Macro.account_id == account_id)
        .where(
            or_(
                Macro.visibility == MACRO_VISIBILITY_GLOBAL,
                (Macro.visibility == MACRO_VISIBILITY_PERSONAL)
                & (Macro.created_by_id == user_id),
            )
        )
        .order_by(Macro.id)  # type: ignore[arg-type]
    )
    return list((await session.exec(stmt)).all())


async def fetch_macro_visible_to_user(
    session: AsyncSession,
    *,
    account_id: int,
    macro_id: int,
    user_id: int,
) -> Macro | None:
    """``MacroPolicy#show?`` — global OR author."""
    macro = (
        await session.exec(
            select(Macro).where(
                Macro.id == macro_id,
                Macro.account_id == account_id,
            )
        )
    ).first()
    if macro is None:
        return None
    if macro.visibility == MACRO_VISIBILITY_GLOBAL:
        return macro
    if macro.created_by_id == user_id:
        return macro
    return None


# ---------------------------------------------------------------------------
# Authorization helpers
# ---------------------------------------------------------------------------
async def _user_is_admin(
    session: AsyncSession, *, account_id: int, user_id: int
) -> bool:
    row = (
        await session.exec(
            select(AccountUser).where(
                AccountUser.account_id == account_id,
                AccountUser.user_id == user_id,
                AccountUser.role == ACCOUNT_USER_ROLE_ADMINISTRATOR,
            )
        )
    ).first()
    return row is not None


def _clamp_visibility_for_role(
    *, requested: int, is_admin: bool
) -> int:
    """``Macro#set_visibility`` — agents are forced to ``personal``
    regardless of what they submit."""
    return requested if is_admin else MACRO_VISIBILITY_PERSONAL


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def create_macro(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int,
    payload: dict[str, Any],
) -> Macro:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Name can't be blank"},
        )
    actions = _validate_actions(payload.get("actions"))
    requested_vis = macro_visibility_from_str(payload.get("visibility"))
    is_admin = await _user_is_admin(
        session, account_id=account_id, user_id=user_id
    )
    clamped_vis = _clamp_visibility_for_role(
        requested=requested_vis, is_admin=is_admin
    )

    macro = Macro(
        account_id=account_id,
        name=name,
        visibility=clamped_vis,
        actions=actions,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    session.add(macro)
    await session.flush()
    await session.refresh(macro)
    return macro


async def update_macro(
    session: AsyncSession,
    *,
    macro: Macro,
    user_id: int,
    payload: dict[str, Any],
) -> Macro:
    if "name" in payload:
        new_name = (payload.get("name") or "").strip()
        if not new_name:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "Name can't be blank"},
            )
        macro.name = new_name
    if "actions" in payload:
        macro.actions = _validate_actions(payload.get("actions"))
    if "visibility" in payload:
        requested = macro_visibility_from_str(payload.get("visibility"))
        is_admin = await _user_is_admin(
            session, account_id=macro.account_id, user_id=user_id
        )
        macro.visibility = _clamp_visibility_for_role(
            requested=requested, is_admin=is_admin
        )
    macro.updated_by_id = user_id

    session.add(macro)
    await session.flush()
    await session.refresh(macro)
    return macro


async def destroy_macro(session: AsyncSession, *, macro: Macro) -> None:
    await session.delete(macro)
    await session.flush()


# ---------------------------------------------------------------------------
# Authorization for write/destroy/execute
# ---------------------------------------------------------------------------
async def can_user_modify_macro(
    session: AsyncSession,
    *,
    macro: Macro,
    user_id: int,
) -> bool:
    """``MacroPolicy#update?`` — author OR (admin AND macro.global)."""
    if macro.created_by_id == user_id:
        return True
    if macro.visibility == MACRO_VISIBILITY_GLOBAL:
        return await _user_is_admin(
            session, account_id=macro.account_id, user_id=user_id
        )
    return False


async def can_user_destroy_macro(
    session: AsyncSession,
    *,
    macro: Macro,
    user_id: int,
) -> bool:
    """``MacroPolicy#destroy?`` — author OR orphan-and-admin (the macro
    has no creator AND it's a global macro AND the user is admin)."""
    if macro.created_by_id == user_id:
        return True
    if macro.created_by_id is None and macro.visibility == MACRO_VISIBILITY_GLOBAL:
        return await _user_is_admin(
            session, account_id=macro.account_id, user_id=user_id
        )
    return False


async def can_user_execute_macro(
    session: AsyncSession,
    *,
    macro: Macro,
    user_id: int,
) -> bool:
    """``MacroPolicy#execute?`` — global OR author."""
    return (
        macro.visibility == MACRO_VISIBILITY_GLOBAL
        or macro.created_by_id == user_id
    )


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------
async def execute_macro_on_conversations(
    session: AsyncSession,
    *,
    macro: Macro,
    conversation_ids: list[int],
    user_id: int,
) -> int:
    """Run ``macro.actions`` against each conversation_id in scope.

    Returns the number of conversations the actions ran against
    (informational — Chatwoot's controller doesn't surface this; we
    log it). Per-conversation errors are swallowed inside
    :class:`ActionExecutor` so a single bad row doesn't abort the rest.
    """
    if not conversation_ids:
        return 0
    rows = list(
        (
            await session.exec(
                select(Conversation).where(
                    Conversation.account_id == macro.account_id,
                    Conversation.id.in_(conversation_ids),  # type: ignore[union-attr]
                )
            )
        ).all()
    )
    for conv in rows:
        executor = MacroExecutor(
            session,
            conversation=conv,
            executing_user_id=user_id,
        )
        await executor.execute(list(macro.actions or []))
    return len(rows)


__all__ = [
    "can_user_destroy_macro",
    "can_user_execute_macro",
    "can_user_modify_macro",
    "create_macro",
    "destroy_macro",
    "execute_macro_on_conversations",
    "fetch_macro_visible_to_user",
    "list_macros_for_user",
    "update_macro",
]
