"""JSON shapes for publications, their targets and publishable channels."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.media_library import service as media_library
from app.domains.publishing.models import (
    Publication,
    PublicationSet,
    PublicationTarget,
    PublishingChannel,
    PublishingSignature,
)
from app.domains.publishing.service import channels_by_id, targets_by_publication


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def present_channel(channel: PublishingChannel) -> dict[str, Any]:
    """Never includes ``credentials``."""
    return {
        "id": channel.id,
        "network": channel.network,
        "name": channel.name,
        "username": channel.username,
        "avatar_url": channel.avatar_url,
        "inbox_id": channel.inbox_id,
        "status": channel.status,
        "status_message": channel.status_message,
    }


def _present_target(
    target: PublicationTarget, channel: PublishingChannel | None
) -> dict[str, Any]:
    return {
        "id": target.id,
        "channel": (
            present_channel(channel)
            if channel is not None
            else {"id": target.channel_id, "network": target.network, "name": None}
        ),
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
    channels: dict[int, PublishingChannel],
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
        "targets": [_present_target(t, channels.get(t.channel_id)) for t in targets],
    }


async def present_publications(
    session: AsyncSession, publications: list[Publication]
) -> list[dict[str, Any]]:
    """Batch-loads targets and their channels (no query per row)."""
    ids = [p.id for p in publications if p.id is not None]
    targets = await targets_by_publication(session, publication_ids=ids)
    channels = await channels_by_id(
        session,
        channel_ids=list({t.channel_id for group in targets.values() for t in group}),
    )
    return [
        present_publication(p, targets.get(p.id, []), channels)  # type: ignore[arg-type]
        for p in publications
    ]


async def present_one_publication(
    session: AsyncSession, publication: Publication
) -> dict[str, Any]:
    return (await present_publications(session, [publication]))[0]



def present_signature(signature: PublishingSignature) -> dict[str, Any]:
    return {
        "id": signature.id,
        "content": signature.content,
        "auto_add": signature.auto_add,
        "created_at": _iso(signature.created_at),
        "updated_at": _iso(signature.updated_at),
    }


async def present_sets(
    session: AsyncSession, sets: list[PublicationSet]
) -> list[dict[str, Any]]:
    """Batch-loads the sets' channels and library files. A channel removed
    since the set was saved shows as ``null``; a library file, with its
    one-hour preview link."""
    payloads = [s.payload or {} for s in sets]
    channels = await channels_by_id(
        session,
        channel_ids=list(
            {t["channel_id"] for p in payloads for t in p.get("targets") or []}
        ),
    )
    assets = {}
    if sets:
        assets = await media_library.get_assets(
            session,
            account_id=sets[0].account_id,
            asset_ids=[
                m["media_id"]
                for p in payloads
                for m in p.get("media") or []
                if m.get("media_id") is not None
            ],
        )

    def media(item: dict[str, Any]) -> dict[str, Any]:
        asset = assets.get(item.get("media_id")) if item.get("media_id") else None
        if asset is not None:
            return {
                "media_id": asset.id,
                "type": asset.kind,
                "url": media_library.asset_preview_url(asset),
            }
        return item

    return [
        {
            "id": s.id,
            "name": s.name,
            "content": p.get("content"),
            "media": [media(m) for m in p.get("media") or []],
            "targets": [
                {
                    "channel_id": t["channel_id"],
                    "channel": (
                        present_channel(channels[t["channel_id"]])
                        if t["channel_id"] in channels
                        else None
                    ),
                    "settings": t.get("settings") or {},
                    "content_override": t.get("content_override"),
                }
                for t in p.get("targets") or []
            ],
            "created_at": _iso(s.created_at),
            "updated_at": _iso(s.updated_at),
        }
        for s, p in zip(sets, payloads, strict=True)
    ]

__all__ = [
    "present_channel",
    "present_one_publication",
    "present_publication",
    "present_publications",
    "present_sets",
    "present_signature",
]
