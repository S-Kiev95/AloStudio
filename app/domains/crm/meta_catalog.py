"""Products → a Meta catalogue (Commerce Manager), F11.

An admin links the account to a catalogue by pasting its id and a token
with ``catalog_management`` (a system user's, from Business Settings). The
link lives in an ``integrations_hooks`` row (``app_id="meta_catalog"``),
like the Meta Ads one: ``settings`` keeps the catalogue id and name, the
last sync's outcome and the items waiting to be removed.

A sync sends every product in one ``items_batch`` call: enabled ones are
upserted, disabled or deleted ones removed. Meta validates the batch after
answering, so the outcome is read back from ``check_batch_request_status``
for a few seconds; whatever is still pending then shows as sent.

Products need what Meta requires of every item (title, description, price
with currency, a link and an image); those missing something are not sent
and say why. The brand Meta also asks for is the account's name.

What happens with the catalogue on WhatsApp (product messages, orders) is
the WhatsApp channel's business: see ``PENDIENTES-POR-FASE.md``, F11.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.accounts.models import Account
from app.domains.instagram.graph import graph_base
from app.domains.integrations.models import IntegrationsHook
from app.domains.products.models import Product

log = logging.getLogger(__name__)

APP_ID = "meta_catalog"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# How long a manual sync waits for Meta to validate the batch.
STATUS_POLLS = 5
STATUS_POLL_SECONDS = 2.0


class CatalogError(Exception):
    """Meta refused the call. ``code`` is ours, for the panel."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


# ---------------------------------------------------------------------------
# The link
# ---------------------------------------------------------------------------
async def get_link(session: AsyncSession, account_id: int) -> IntegrationsHook | None:
    return (
        await session.exec(
            select(IntegrationsHook).where(
                IntegrationsHook.account_id == account_id,
                IntegrationsHook.app_id == APP_ID,
            )
        )
    ).first()


def _settings(hook: IntegrationsHook) -> dict[str, Any]:
    return dict(hook.settings or {})


async def _graph(
    method: str, path: str, *, token: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.request(
                method,
                f"{graph_base()}/{path}",
                params={**(params or {}), "access_token": token}
                if method == "GET"
                else {"access_token": token},
                data=None if method == "GET" else params,
            )
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CatalogError("unreachable", type(exc).__name__) from exc
    if resp.status_code >= 400 or "error" in body:
        error = body.get("error") if isinstance(body, dict) else None
        message = error.get("message") if isinstance(error, dict) else None
        code = "token" if isinstance(error, dict) and error.get("code") in (190, 102) else "refused"
        if isinstance(error, dict) and error.get("code") in (10, 200, 294):
            code = "permission"
        raise CatalogError(code, message)
    return body if isinstance(body, dict) else {}


async def connect(
    session: AsyncSession, *, account_id: int, catalog_id: str, access_token: str | None
) -> IntegrationsHook:
    """Check the catalogue answers with this token, then keep the link.
    Without a new token, the stored one is reused (changing the id only)."""
    catalog_id = catalog_id.strip()
    if not catalog_id.isdigit():
        raise CatalogError("catalog_id")
    hook = await get_link(session, account_id)
    token = (access_token or "").strip() or (hook.access_token if hook else None)
    if not token:
        raise CatalogError("token")
    info = await _graph("GET", catalog_id, token=token, params={"fields": "id,name"})
    if hook is None:
        hook = IntegrationsHook(account_id=account_id, app_id=APP_ID, hook_type=0, status=1)
    settings = _settings(hook) if hook.id else {}
    if settings.get("catalog_id") != catalog_id:
        settings.pop("last_sync", None)
    settings.update({"catalog_id": catalog_id, "catalog_name": info.get("name")})
    hook.settings = settings
    hook.reference_id = catalog_id
    hook.access_token = token
    session.add(hook)
    await session.flush()
    return hook


async def disconnect(session: AsyncSession, account_id: int) -> None:
    hook = await get_link(session, account_id)
    if hook is not None:
        await session.delete(hook)
    rows = await session.exec(select(Product).where(Product.account_id == account_id))
    for product in rows.all():
        product.meta_synced_at = None
        product.meta_sync_error = None
        product.meta_retailer_id = None
        session.add(product)
    await session.flush()


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------
def retailer_id(product: Product) -> str:
    return product.meta_retailer_id or (product.sku or "").strip() or f"alo-{product.id}"


def missing_fields(product: Product) -> list[str]:
    """What Meta needs that the product doesn't have."""
    missing = []
    if not (product.description or "").strip():
        missing.append("description")
    if product.price is None or not product.currency:
        missing.append("price")
    if not (product.url or "").startswith(("http://", "https://")):
        missing.append("url")
    if not (product.image_url or "").startswith(("http://", "https://")):
        missing.append("image_url")
    return missing


def item_data(product: Product, *, brand: str) -> dict[str, Any]:
    return {
        "id": retailer_id(product),
        "title": product.name[:150],
        "description": (product.description or "").strip()[:9999],
        "availability": "in stock",
        "condition": "new",
        "price": f"{product.price:.2f} {(product.currency or '').upper()}",
        "link": product.url,
        "image_link": product.image_url,
        "brand": brand[:100],
    }


@dataclass
class SyncResult:
    sent: int = 0
    removed: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "sent": self.sent,
            "removed": self.removed,
            "skipped": self.skipped,
            "failed": self.failed,
        }


def queue_removal(hook: IntegrationsHook, product: Product) -> None:
    """Remember a synced product that is going away, for the next sync."""
    if not product.meta_retailer_id:
        return
    settings = _settings(hook)
    pending = [*settings.get("pending_removals", [])]
    if product.meta_retailer_id not in pending:
        pending.append(product.meta_retailer_id)
    settings["pending_removals"] = pending
    hook.settings = settings


async def _batch_errors(catalog_id: str, token: str, handle: str) -> dict[str, str] | None:
    """``{retailer_id: message}`` once Meta has validated the batch, or
    ``None`` if it is still working on it."""
    for attempt in range(STATUS_POLLS):
        if attempt:
            await asyncio.sleep(STATUS_POLL_SECONDS)
        body = await _graph(
            "GET",
            f"{catalog_id}/check_batch_request_status",
            token=token,
            params={"handle": handle},
        )
        rows = body.get("data") or []
        status = rows[0] if rows and isinstance(rows[0], dict) else {}
        if status.get("status") in ("finished", "error"):
            errors: dict[str, str] = {}
            for err in status.get("errors") or []:
                if isinstance(err, dict) and err.get("id"):
                    errors[str(err["id"])] = str(err.get("message") or "error")
            return errors
    return None


async def sync(session: AsyncSession, account_id: int) -> SyncResult:
    """Send the account's products to its catalogue. The caller commits."""
    hook = await get_link(session, account_id)
    if hook is None or not hook.access_token:
        raise CatalogError("not_connected")
    settings = _settings(hook)
    catalog_id = str(settings.get("catalog_id") or "")
    account = await session.get(Account, account_id)
    brand = (account.name if account else "") or "AloStudio"

    result = SyncResult()
    requests: list[dict[str, Any]] = []
    upserts: dict[str, Product] = {}
    products = list(
        (await session.exec(select(Product).where(Product.account_id == account_id))).all()
    )
    for product in products:
        if not product.enabled:
            if product.meta_retailer_id:
                requests.append({"method": "DELETE", "data": {"id": product.meta_retailer_id}})
                product.meta_retailer_id = None
                product.meta_synced_at = None
                result.removed += 1
            product.meta_sync_error = None
            session.add(product)
            continue
        missing = missing_fields(product)
        if missing:
            product.meta_sync_error = "missing:" + ",".join(missing)
            session.add(product)
            result.skipped += 1
            continue
        data = item_data(product, brand=brand)
        requests.append({"method": "UPDATE", "data": data})
        upserts[data["id"]] = product
    for rid in settings.get("pending_removals", []):
        requests.append({"method": "DELETE", "data": {"id": rid}})
        result.removed += 1

    errors: dict[str, str] | None = {}
    if requests:
        body = await _graph(
            "POST",
            f"{catalog_id}/items_batch",
            token=hook.access_token,
            params={
                "item_type": "PRODUCT_ITEM",
                "allow_upsert": "true",
                "requests": json.dumps(requests),
            },
        )
        handles = body.get("handles") or []
        if handles:
            errors = await _batch_errors(catalog_id, hook.access_token, str(handles[0]))

    now = datetime.now(UTC)
    for rid, product in upserts.items():
        message = (errors or {}).get(rid)
        product.meta_retailer_id = rid
        if message:
            product.meta_sync_error = message[:1000]
            result.failed += 1
        else:
            product.meta_sync_error = None
            product.meta_synced_at = now
            result.sent += 1
        session.add(product)

    settings["pending_removals"] = []
    settings["last_sync"] = {
        "at": int(now.timestamp()),
        "validated": errors is not None,
        **result.as_dict(),
    }
    hook.settings = settings
    session.add(hook)
    await session.flush()
    log.info("crm.meta_catalog.synced account_id=%s %s", account_id, result.as_dict())
    return result


# How long after a product changes the catalogue is updated: a few edits in
# a row end up in one sync (the job id is per account).
SYNC_DELAY_SECONDS = 30


async def enqueue_sync(account_id: int) -> None:
    """Sync the account's catalogue shortly, off the request. Best-effort:
    without a worker the next manual sync catches up."""
    from app.core.config import get_settings

    settings = get_settings()
    if settings.app_env == "test":
        return
    from arq import create_pool
    from arq.connections import RedisSettings

    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.arq_redis_url))
        try:
            await pool.enqueue_job(
                "sync_meta_catalog_task",
                account_id,
                _job_id=f"meta-catalog-{account_id}",
                _defer_by=SYNC_DELAY_SECONDS,
            )
        finally:
            await pool.aclose()
    except Exception as exc:  # noqa: BLE001 - optional side job, never fail the save
        log.warning(
            "crm.meta_catalog.enqueue_failed account_id=%s err=%s",
            account_id,
            type(exc).__name__,
        )


async def product_changed(
    session: AsyncSession, product: Product, *, deleted: bool = False
) -> None:
    """After a product is saved or deleted: keep the catalogue in step."""
    hook = await get_link(session, product.account_id)
    if hook is None:
        return
    if deleted:
        queue_removal(hook, product)
        session.add(hook)
        await session.flush()
    await enqueue_sync(product.account_id)


def present_link(hook: IntegrationsHook | None) -> dict[str, Any]:
    if hook is None:
        return {"connected": False}
    settings = _settings(hook)
    return {
        "connected": True,
        "catalog_id": settings.get("catalog_id"),
        "catalog_name": settings.get("catalog_name"),
        "last_sync": settings.get("last_sync"),
    }


__all__ = [
    "APP_ID",
    "CatalogError",
    "SyncResult",
    "connect",
    "disconnect",
    "enqueue_sync",
    "get_link",
    "missing_fields",
    "present_link",
    "product_changed",
    "queue_removal",
    "sync",
]
