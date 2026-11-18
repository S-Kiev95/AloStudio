"""ARQ task where AloStudio's AI answers a customer (PLAN.agente-ia.md, 2b).

Queued by :mod:`app.domains.ai_agent.service` for each customer message once
the transaction that saved it commits (dropped if it rolls back, like the
webhook deliveries in :mod:`app.domains.webhooks.listener`), and run a few
seconds later so a burst of messages ends up with one answer: each run gives
up unless its message is still the last one. The model call takes seconds,
so it never runs inside the webhook.

A run that can't happen (no queue) or crashes hands a conversation the live
AI held to the team, so no customer is left waiting on it.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session
from sqlmodel.ext.asyncio.session import AsyncSession

log = logging.getLogger(__name__)

# The customer often sends a thought in two or three messages.
_REPLY_DELAY = timedelta(seconds=4)

_PENDING_KEY = "ai_replies_after_commit"
_in_flight: set[asyncio.Task[None]] = set()


def enqueue_after_commit(session: AsyncSession, *, conversation_id: int, message_id: int) -> None:
    """Queue the run when this session's transaction commits."""
    sync = session.sync_session
    transaction = sync.get_nested_transaction() or sync.get_transaction()
    sync.info.setdefault(_PENDING_KEY, []).append((transaction, (conversation_id, message_id)))


def _within(transaction: Any, closed: Any) -> bool:
    while transaction is not None:
        if transaction is closed:
            return True
        transaction = transaction.parent
    return False


@event.listens_for(Session, "after_soft_rollback")
def _drop_rolled_back(session: Session, previous_transaction: Any) -> None:
    pending = session.info.get(_PENDING_KEY)
    if pending:
        session.info[_PENDING_KEY] = [
            (tx, run) for tx, run in pending if not _within(tx, previous_transaction)
        ]


@event.listens_for(Session, "after_commit")
def _enqueue_committed(session: Session) -> None:
    pending = session.info.pop(_PENDING_KEY, None)
    if not pending:
        return
    runs = list(dict.fromkeys(run for _, run in pending))
    task = asyncio.get_running_loop().create_task(_enqueue_all(runs))
    _in_flight.add(task)
    task.add_done_callback(_in_flight.discard)


async def _enqueue_all(runs: list[tuple[int, int]]) -> None:
    for conversation_id, message_id in runs:
        if not await enqueue_ai_reply(conversation_id=conversation_id, message_id=message_id):
            await _rescue(None, conversation_id)


async def enqueue_ai_reply(*, conversation_id: int, message_id: int) -> bool:
    """Queue the run; False when there is no queue."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    try:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().arq_redis_url))
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "ai_agent.no_pool conversation=%s message=%s err=%s",
            conversation_id,
            message_id,
            exc,
        )
        return False
    try:
        await pool.enqueue_job(
            "ai_reply_task",
            conversation_id,
            message_id,
            _job_id=f"ai_reply:{conversation_id}:{message_id}",
            _defer_by=_REPLY_DELAY,
        )
    finally:
        await pool.aclose()
    return True


def _factory(ctx: dict[str, Any] | None) -> Any:
    from app.core.db import get_session_factory

    engine = ctx.get("engine") if isinstance(ctx, dict) else None
    if engine is None:
        return get_session_factory()
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


async def _rescue(ctx: dict[str, Any] | None, conversation_id: int) -> None:
    """Hand the conversation to the team if the live AI still holds it."""
    from app.domains.ai_agent.service import rescue

    try:
        async with _factory(ctx)() as session:
            await rescue(session, conversation_id)
            await session.commit()
    except Exception:
        log.exception("ai_agent.rescue_failed conversation=%s", conversation_id)


async def ai_reply_task(ctx: dict[str, Any], conversation_id: int, message_id: int) -> dict[str, Any]:
    """Run :func:`app.domains.ai_agent.service.answer` in its own session."""
    from app.domains.ai_agent.service import answer

    async with _factory(ctx)() as session:
        try:
            reply = await answer(session, conversation_id=conversation_id, message_id=message_id)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("ai_agent.reply_failed conversation=%s", conversation_id)
            await _rescue(ctx, conversation_id)
            return {"conversation_id": conversation_id, "outcome": "error"}
    outcome = reply.status if reply is not None else "skipped"
    log.info("ai_agent.reply conversation=%s outcome=%s", conversation_id, outcome)
    return {"conversation_id": conversation_id, "outcome": outcome}


__all__ = ["ai_reply_task", "enqueue_after_commit", "enqueue_ai_reply"]
