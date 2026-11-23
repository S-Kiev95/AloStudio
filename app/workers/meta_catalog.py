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
    from app.domains.crm.meta_catalog import CatalogError, record_error, sync

    async with _session_factory(ctx)() as session:
        try:
            result = await sync(session, account_id)
        except CatalogError as exc:
            failed = exc
        else:
            await session.commit()
            return {"ok": True, **result.as_dict()}
    # Not linked any more, or Meta refused the token: kept on the link (in a
    # fresh session, the failed sync is dropped) so the panel shows it.
    log.warning("crm.meta_catalog.task_failed account_id=%s code=%s", account_id, failed.code)
    async with _session_factory(ctx)() as session:
        await record_error(session, account_id, failed.code)
        await session.commit()
    return {"ok": False, "code": failed.code}


__all__ = ["sync_meta_catalog_task"]
