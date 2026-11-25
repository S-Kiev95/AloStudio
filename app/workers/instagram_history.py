"""ARQ task: import an Instagram account's past DMs right after it connects.

Enqueued by :func:`app.domains.instagram.history.enqueue_import`.
"""

from __future__ import annotations

import logging
from typing import Any

from app.workers.contact_avatars import _session_factory

log = logging.getLogger(__name__)


async def import_instagram_history_task(
    ctx: dict[str, Any], channel_instagram_id: int
) -> dict[str, Any]:
    from app.domains.instagram.history import HistoryError, import_history

    async with _session_factory(ctx)() as session:
        try:
            result = await import_history(session, channel_instagram_id)
        except HistoryError as exc:
            # Kept in the log: the account works anyway, only the past is missing.
            log.warning(
                "instagram.history.task_failed channel_id=%s err=%s", channel_instagram_id, exc
            )
            return {"ok": False, "error": str(exc)}
        await session.commit()
    return {"ok": True, **result}


__all__ = ["import_instagram_history_task"]
