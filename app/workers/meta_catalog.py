"""ARQ task: send an account's products to its Meta catalogue (F11).

Enqueued, deferred a few seconds, when a product changes; see
:mod:`app.domains.crm.meta_catalog`.
"""

from __future__ import annotations

import logging
from typing import Any

from app.workers.contact_avatars import _session_factory

log = logging.getLogger(__name__)


async def sync_meta_catalog_task(ctx: dict[str, Any], account_id: int) -> dict[str, Any]:
    from app.domains.crm.meta_catalog import CatalogError, sync

    async with _session_factory(ctx)() as session:
        try:
            result = await sync(session, account_id)
        except CatalogError as exc:
            # Not linked any more, or Meta refused the token: the panel shows
            # it on the next manual sync.
            log.warning("crm.meta_catalog.task_failed account_id=%s code=%s", account_id, exc.code)
            return {"ok": False, "code": exc.code}
        await session.commit()
    return {"ok": True, **result.as_dict()}


__all__ = ["sync_meta_catalog_task"]
