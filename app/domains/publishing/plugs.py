"""Plugs — automatic actions on a channel's own posts once they reach a
number of likes (reply with a message, repost…).

Which actions exist is up to each network's adapter (``plug_kinds``);
nothing here names a network. They are checked right after the hourly
refresh of post figures, on the posts of the last 30 days: a post whose
``likes`` reached the plug's threshold gets the action once — every attempt,
good or failed, is recorded per plug and post, so it is never repeated.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.publishing import service as svc
from app.domains.publishing.adapters import PlugKind, adapter_for_network, all_adapters
from app.domains.publishing.analytics import POST_WINDOW
from app.domains.publishing.models import (
    CHANNEL_STATUS_ACTIVE,
    TARGET_STATE_PUBLISHED,
    PublicationTarget,
    PublishingChannel,
    PublishingPlug,
    PublishingPlugRun,
)

log = logging.getLogger(__name__)

# Runs per job at most; the rest wait for the next hour.
MAX_RUNS_PER_JOB = 50
THRESHOLD_MAX = 1_000_000


def catalog() -> list[dict[str, Any]]:
    """Every network's plugs, for the screen that sets them up."""
    return [
        {"network": adapter.network, "kinds": [asdict(k) for k in adapter.plug_kinds]}
        for adapter in all_adapters()
        if adapter.plug_kinds
    ]


def _kind(network: str, kind: str) -> PlugKind | None:
    adapter = adapter_for_network(network)
    return next((k for k in adapter.plug_kinds if k.kind == kind), None) if adapter else None


async def list_plugs(session: AsyncSession, *, account_id: int) -> list[PublishingPlug]:
    return list(
        (
            await session.exec(
                select(PublishingPlug)
                .where(PublishingPlug.account_id == account_id)
                .order_by(col(PublishingPlug.id))
            )
        ).all()
    )


async def get_plug(
    session: AsyncSession, *, account_id: int, plug_id: int
) -> PublishingPlug | None:
    plug = await session.get(PublishingPlug, plug_id)
    if plug is None or plug.account_id != account_id:
        return None
    return plug


async def save_plug(
    session: AsyncSession, *, plug: PublishingPlug, values: dict[str, Any]
) -> PublishingPlug:
    """Create or edit; ``values`` has only the fields being set."""
    if values.get("channel_id") is not None and plug.id is None:
        channel = await session.get(PublishingChannel, values["channel_id"])
        if channel is None or channel.account_id != plug.account_id:
            raise svc._unprocessable("El canal no existe o no pertenece a esta cuenta")
        plug.channel_id = channel.id  # type: ignore[assignment]
        plug.kind = values.get("kind") or ""
    channel = await session.get(PublishingChannel, plug.channel_id)
    kind = _kind(channel.network, plug.kind) if channel else None
    if kind is None:
        raise svc._unprocessable("Esa red no tiene esa acción automática")
    if values.get("likes_threshold") is not None:
        if not 1 <= values["likes_threshold"] <= THRESHOLD_MAX:
            raise svc._unprocessable("La cantidad de me gusta tiene que ser al menos 1")
        plug.likes_threshold = values["likes_threshold"]
    if "message" in values:
        plug.message = (values["message"] or "").strip() or None
    if values.get("active") is not None:
        plug.active = values["active"]
    if kind.message_max is not None:
        if not plug.message:
            raise svc._unprocessable("Esta acción necesita el mensaje que va a publicar")
        # Measured as the network will count it when the plug runs, or a
        # message accepted here would only fail then.
        adapter = adapter_for_network(channel.network) if channel else None
        length = adapter.text_length(plug.message) if adapter else len(plug.message)
        if length > kind.message_max:
            raise svc._unprocessable(
                f"El mensaje supera los {kind.message_max} caracteres"
            )
    else:
        plug.message = None
    exists = (
        await session.exec(
            select(PublishingPlug.id).where(
                PublishingPlug.channel_id == plug.channel_id,
                PublishingPlug.kind == plug.kind,
                col(PublishingPlug.id) != plug.id,
            )
        )
    ).first()
    if exists is not None:
        raise svc._unprocessable("Ese canal ya tiene esa acción automática")
    session.add(plug)
    await session.flush()
    await session.refresh(plug)
    return plug


async def delete_plug(session: AsyncSession, *, plug: PublishingPlug) -> None:
    await session.delete(plug)
    await session.flush()


async def run_due_plugs(
    session: AsyncSession, *, now: datetime | None = None, limit: int = MAX_RUNS_PER_JOB
) -> int:
    """Fire the active plugs on the recent posts that reached their
    threshold and haven't had them yet, committing each run. Returns how
    many ran (good or failed)."""
    now = now or datetime.now(UTC)
    rows = (
        await session.exec(
            select(PublishingPlug, PublicationTarget)
            .join(PublicationTarget, PublicationTarget.channel_id == PublishingPlug.channel_id)  # type: ignore[arg-type]
            .join(PublishingChannel, PublishingChannel.id == PublishingPlug.channel_id)  # type: ignore[arg-type]
            .where(
                col(PublishingPlug.active).is_(True),
                PublishingChannel.status == CHANNEL_STATUS_ACTIVE,
                PublicationTarget.state == TARGET_STATE_PUBLISHED,
                col(PublicationTarget.external_id).is_not(None),
                col(PublicationTarget.published_at) >= now - POST_WINDOW,
                col(PublicationTarget.id).not_in(
                    select(PublishingPlugRun.target_id).where(
                        PublishingPlugRun.plug_id == PublishingPlug.id
                    )
                ),
            )
            .order_by(col(PublicationTarget.published_at))
        )
    ).all()
    due = [
        (plug.id, target.id)
        for plug, target in rows
        if isinstance((target.metrics or {}).get("likes"), int)
        and target.metrics["likes"] >= plug.likes_threshold
    ][:limit]

    ran = 0
    for plug_id, target_id in due:
        try:
            plug = await session.get(PublishingPlug, plug_id)
            target = await session.get(PublicationTarget, target_id)
            channel = await session.get(PublishingChannel, plug.channel_id) if plug else None
            adapter = adapter_for_network(channel.network) if channel else None
            if plug is None or target is None or adapter is None:
                continue
            try:
                result = await adapter.run_plug(
                    session, kind=plug.kind, target=target, message=plug.message
                )
                ok, external_id, error = result.ok, result.external_id, result.error_message
            except Exception:
                log.exception("publishing.plug.crashed plug_id=%s target_id=%s", plug_id, target_id)
                ok, external_id, error = False, None, "Error inesperado al ejecutar la acción."
            session.add(
                PublishingPlugRun(
                    plug_id=plug_id,  # type: ignore[arg-type]
                    target_id=target_id,  # type: ignore[arg-type]
                    ok=ok,
                    external_id=external_id or None,
                    error_message=None if ok else error,
                )
            )
            await session.commit()
            ran += 1
        except Exception:
            # One run must not sink the rest.
            await session.rollback()
            log.exception("publishing.plug.store_failed plug_id=%s target_id=%s", plug_id, target_id)
    return ran


async def runs_by_plug(
    session: AsyncSession, *, plug_ids: list[int]
) -> dict[int, list[PublishingPlugRun]]:
    if not plug_ids:
        return {}
    rows = (
        await session.exec(
            select(PublishingPlugRun)
            .where(col(PublishingPlugRun.plug_id).in_(plug_ids))
            .order_by(col(PublishingPlugRun.id).desc())
        )
    ).all()
    grouped: dict[int, list[PublishingPlugRun]] = {i: [] for i in plug_ids}
    for run in rows:
        grouped[run.plug_id].append(run)
    return grouped


__all__ = [
    "catalog",
    "delete_plug",
    "get_plug",
    "list_plugs",
    "run_due_plugs",
    "runs_by_plug",
    "save_plug",
]
