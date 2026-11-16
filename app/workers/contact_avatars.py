"""ARQ tasks for contact profile pictures (F14).

``refresh_contact_avatar_task`` is enqueued, deferred a few seconds, when a
new Instagram or Messenger contact writes; ``refresh_stale_avatars_task``
runs daily for contacts still active. See :mod:`app.domains.contacts.avatar`.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

log = logging.getLogger(__name__)


def _session_factory(ctx: dict[str, Any]) -> Any:
    from app.core.db import get_session_factory

    engine = ctx.get("engine") if isinstance(ctx, dict) else None
    if engine is None:
        return get_session_factory()
    return async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


async def refresh_contact_avatar_task(
    ctx: dict[str, Any], contact_id: int
) -> dict[str, Any]:
    from app.domains.contacts.avatar import refresh_avatar
    from app.domains.contacts.models import Contact

    async with _session_factory(ctx)() as session:
        contact = await session.get(Contact, contact_id)
        if contact is None:
            # The webhook's transaction rolled back; nothing to do.
            return {"stored": False, "reason": "contact_gone"}
        stored = await refresh_avatar(session, contact)
        await session.commit()
    return {"stored": stored}


async def refresh_stale_avatars_task(ctx: dict[str, Any]) -> dict[str, int]:
    from app.domains.contacts.avatar import refresh_avatar, stale_contact_ids
    from app.domains.contacts.models import Contact

    stored = 0
    async with _session_factory(ctx)() as session:
        ids = await stale_contact_ids(session)
        for contact_id in ids:
            contact = await session.get(Contact, contact_id)
            if contact is None:
                continue
            try:
                stored += int(await refresh_avatar(session, contact))
                # One commit per contact: a failure later in the batch keeps
                # what was already done.
                await session.commit()
            except Exception as exc:  # noqa: BLE001 - one bad contact can't stop the batch
                await session.rollback()
                log.warning(
                    "contacts.avatar.refresh_failed contact_id=%s err=%s",
                    contact_id,
                    type(exc).__name__,
                )
    log.info("contacts.avatar.daily checked=%s stored=%s", len(ids), stored)
    return {"checked": len(ids), "stored": stored}


__all__ = ["refresh_contact_avatar_task", "refresh_stale_avatars_task"]
