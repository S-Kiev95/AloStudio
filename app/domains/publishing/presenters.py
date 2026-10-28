"""JSON shapes for publications, their targets and publishable channels."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.inboxes.models import Inbox
from app.domains.publishing.adapters import adapter_for_network
from app.domains.publishing.models import Publication, PublicationTarget
from app.domains.publishing.service import targets_by_publication


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def present_channel(inbox: Inbox, network: str) -> dict[str, Any]:
    adapter = adapter_for_network(network)
    label = adapter.channel_label(inbox) if adapter else {"name": inbox.name}
    return {"inbox_id": inbox.id, "network": network, **label}


def _present_target(
    target: PublicationTarget, inbox: Inbox | None
) -> dict[str, Any]:
    channel = (
        present_channel(inbox, target.network)
        if inbox is not None
        else {"inbox_id": target.inbox_id, "network": target.network, "name": None}
    )
    return {
        "id": target.id,
        "channel": channel,
        "settings": target.settings or {},
        "content_override": target.content_override,
        "state": target.state,
        "external_id": target.external_id,
        "permalink": target.permalink,
        "error_code": target.error_code,
        "error_message": target.error_message,
        "attempts": target.attempts,
        "published_at": _iso(target.published_at),
        "metrics": target.metrics or {},
        "metrics_updated_at": _iso(target.metrics_updated_at),
        "metrics_error": target.metrics_error,
    }


def present_publication(
    publication: Publication,
    targets: list[PublicationTarget],
    inboxes: dict[int, Inbox],
) -> dict[str, Any]:
    return {
        "id": publication.id,
        "account_id": publication.account_id,
        "content": publication.content,
        "media": publication.media or [],
        "scheduled_for": _iso(publication.scheduled_for),
        "state": publication.state,
        "created_by_id": publication.created_by_id,
        "published_at": _iso(publication.published_at),
        "created_at": _iso(publication.created_at),
        "updated_at": _iso(publication.updated_at),
        "targets": [_present_target(t, inboxes.get(t.inbox_id)) for t in targets],
    }


async def present_publications(
    session: AsyncSession, publications: list[Publication]
) -> list[dict[str, Any]]:
    """Batch-loads targets and their inboxes (no query per row)."""
    ids = [p.id for p in publications if p.id is not None]
    targets = await targets_by_publication(session, publication_ids=ids)
    inbox_ids = {t.inbox_id for group in targets.values() for t in group}
    inboxes: dict[int, Inbox] = {}
    if inbox_ids:
        inboxes = {
            inbox.id: inbox
            for inbox in (
                await session.exec(
                    select(Inbox).where(Inbox.id.in_(inbox_ids))  # type: ignore[union-attr]
                )
            ).all()
        }
    return [
        present_publication(p, targets.get(p.id, []), inboxes)  # type: ignore[arg-type]
        for p in publications
    ]


async def present_one_publication(
    session: AsyncSession, publication: Publication
) -> dict[str, Any]:
    return (await present_publications(session, [publication]))[0]


__all__ = [
    "present_channel",
    "present_one_publication",
    "present_publication",
    "present_publications",
]
