"""AssignmentPolicy CRUD + inbox-linking service.

Ported from ``assignment_policies_controller.rb`` +
``inboxes/assignment_policies_controller.rb`` + the model validations.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.assignment_policies.models import (
    AssignmentPolicy,
    InboxAssignmentPolicy,
    assignment_order_from_str,
    conversation_priority_from_str,
)


def _err(msg: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": msg})


async def _ensure_unique_name(
    session: AsyncSession,
    *,
    account_id: int,
    name: str,
    exclude_id: int | None = None,
) -> None:
    stmt = select(AssignmentPolicy).where(
        AssignmentPolicy.account_id == account_id,
        AssignmentPolicy.name == name,
    )
    if exclude_id is not None:
        stmt = stmt.where(AssignmentPolicy.id != exclude_id)
    if (await session.exec(stmt)).first() is not None:
        raise _err("Name has already been taken")


def _coerce_enums(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    """Map the string enum names to ints, raising 422 on unknown values."""
    order: int | None = None
    priority: int | None = None
    if "assignment_order" in payload and payload["assignment_order"] is not None:
        try:
            order = assignment_order_from_str(payload["assignment_order"])
        except ValueError as exc:
            raise _err("assignment_order is invalid") from exc
    if (
        "conversation_priority" in payload
        and payload["conversation_priority"] is not None
    ):
        try:
            priority = conversation_priority_from_str(
                payload["conversation_priority"]
            )
        except ValueError as exc:
            raise _err("conversation_priority is invalid") from exc
    return order, priority


def _validate_windows(payload: dict[str, Any]) -> None:
    for key in ("fair_distribution_limit", "fair_distribution_window"):
        if key in payload and payload[key] is not None and payload[key] <= 0:
            raise _err(f"{key} must be greater than 0")


async def list_policies(
    session: AsyncSession, *, account_id: int
) -> list[AssignmentPolicy]:
    return list(
        (
            await session.exec(
                select(AssignmentPolicy)
                .where(AssignmentPolicy.account_id == account_id)
                .order_by(AssignmentPolicy.id.asc())  # type: ignore[attr-defined]
            )
        ).all()
    )


async def get_policy(
    session: AsyncSession, *, account_id: int, policy_id: int
) -> AssignmentPolicy | None:
    return (
        await session.exec(
            select(AssignmentPolicy).where(
                AssignmentPolicy.id == policy_id,
                AssignmentPolicy.account_id == account_id,
            )
        )
    ).first()


async def create_policy(
    session: AsyncSession, *, account_id: int, payload: dict[str, Any]
) -> AssignmentPolicy:
    name = (payload.get("name") or "").strip()
    if not name:
        raise _err("Name can't be blank")
    await _ensure_unique_name(session, account_id=account_id, name=name)
    _validate_windows(payload)
    order, priority = _coerce_enums(payload)

    policy = AssignmentPolicy(account_id=account_id, name=name)
    if payload.get("description") is not None:
        policy.description = payload["description"]
    if payload.get("enabled") is not None:
        policy.enabled = bool(payload["enabled"])
    if order is not None:
        policy.assignment_order = order
    if priority is not None:
        policy.conversation_priority = priority
    if payload.get("fair_distribution_limit") is not None:
        policy.fair_distribution_limit = payload["fair_distribution_limit"]
    if payload.get("fair_distribution_window") is not None:
        policy.fair_distribution_window = payload["fair_distribution_window"]

    session.add(policy)
    await session.flush()
    await session.refresh(policy)
    return policy


async def update_policy(
    session: AsyncSession,
    *,
    policy: AssignmentPolicy,
    payload: dict[str, Any],
) -> AssignmentPolicy:
    _validate_windows(payload)
    order, priority = _coerce_enums(payload)

    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            raise _err("Name can't be blank")
        if name != policy.name:
            await _ensure_unique_name(
                session,
                account_id=policy.account_id,
                name=name,
                exclude_id=policy.id,
            )
        policy.name = name
    if "description" in payload:
        policy.description = payload["description"]
    if payload.get("enabled") is not None:
        policy.enabled = bool(payload["enabled"])
    if order is not None:
        policy.assignment_order = order
    if priority is not None:
        policy.conversation_priority = priority
    if payload.get("fair_distribution_limit") is not None:
        policy.fair_distribution_limit = payload["fair_distribution_limit"]
    if payload.get("fair_distribution_window") is not None:
        policy.fair_distribution_window = payload["fair_distribution_window"]

    session.add(policy)
    await session.flush()
    await session.refresh(policy)
    return policy


async def destroy_policy(
    session: AsyncSession, *, policy: AssignmentPolicy
) -> None:
    await session.delete(policy)
    await session.flush()


# ---------------------------------------------------------------------------
# Inbox linking (one policy per inbox)
# ---------------------------------------------------------------------------
async def get_inbox_policy(
    session: AsyncSession, *, inbox_id: int
) -> AssignmentPolicy | None:
    link = (
        await session.exec(
            select(InboxAssignmentPolicy).where(
                InboxAssignmentPolicy.inbox_id == inbox_id
            )
        )
    ).first()
    if link is None:
        return None
    return await session.get(AssignmentPolicy, link.assignment_policy_id)


async def set_inbox_policy(
    session: AsyncSession, *, inbox_id: int, policy: AssignmentPolicy
) -> None:
    """Attach ``policy`` to the inbox, replacing any existing link."""
    await remove_inbox_policy(session, inbox_id=inbox_id)
    session.add(
        InboxAssignmentPolicy(
            inbox_id=inbox_id, assignment_policy_id=policy.id
        )
    )
    await session.flush()


async def remove_inbox_policy(
    session: AsyncSession, *, inbox_id: int
) -> None:
    link = (
        await session.exec(
            select(InboxAssignmentPolicy).where(
                InboxAssignmentPolicy.inbox_id == inbox_id
            )
        )
    ).first()
    if link is not None:
        await session.delete(link)
        await session.flush()


__all__ = [
    "create_policy",
    "destroy_policy",
    "get_inbox_policy",
    "get_policy",
    "list_policies",
    "remove_inbox_policy",
    "set_inbox_policy",
    "update_policy",
]
