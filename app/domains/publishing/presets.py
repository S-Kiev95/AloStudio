"""Signatures and sets — what the composer reuses.

A signature is a saved text the composer adds to a publication; one per
account can be added on its own to every new publication. A set is the
composer saved under a name (text, media and channels with their per-network
settings) so a publication can start from it. Both are only read back by the
composer: publishing never applies them by itself.

A set keeps library media as ``{"media_id"}`` — links are signed when a
publication goes out, so storing one would leave the set with a dead link.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.media_library import service as media_library
from app.domains.publishing import service as svc
from app.domains.publishing.models import (
    MEDIA_TYPES,
    PublicationSet,
    PublishingSignature,
)


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------
async def list_signatures(
    session: AsyncSession, *, account_id: int
) -> list[PublishingSignature]:
    return list(
        (
            await session.exec(
                select(PublishingSignature)
                .where(PublishingSignature.account_id == account_id)
                .order_by(col(PublishingSignature.id))
            )
        ).all()
    )


async def get_signature(
    session: AsyncSession, *, account_id: int, signature_id: int
) -> PublishingSignature | None:
    signature = await session.get(PublishingSignature, signature_id)
    if signature is None or signature.account_id != account_id:
        return None
    return signature


async def save_signature(
    session: AsyncSession,
    *,
    signature: PublishingSignature,
    content: str | None = None,
    auto_add: bool | None = None,
) -> PublishingSignature:
    """Create or edit. Making one added on its own stops the account's
    previous one from being so."""
    if content is not None:
        signature.content = content
    if auto_add is not None:
        signature.auto_add = auto_add
    session.add(signature)
    await session.flush()
    if signature.auto_add:
        await session.exec(  # type: ignore[call-overload]
            update(PublishingSignature)
            .where(
                col(PublishingSignature.account_id) == signature.account_id,
                col(PublishingSignature.id) != signature.id,
                col(PublishingSignature.auto_add).is_(True),
            )
            .values(auto_add=False)
        )
    await session.refresh(signature)
    return signature


async def delete_signature(
    session: AsyncSession, *, signature: PublishingSignature
) -> None:
    await session.delete(signature)
    await session.flush()


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------
async def list_sets(session: AsyncSession, *, account_id: int) -> list[PublicationSet]:
    return list(
        (
            await session.exec(
                select(PublicationSet)
                .where(PublicationSet.account_id == account_id)
                .order_by(col(PublicationSet.name), col(PublicationSet.id))
            )
        ).all()
    )


async def get_set(
    session: AsyncSession, *, account_id: int, set_id: int
) -> PublicationSet | None:
    publication_set = await session.get(PublicationSet, set_id)
    if publication_set is None or publication_set.account_id != account_id:
        return None
    return publication_set


async def _clean_payload(
    session: AsyncSession,
    *,
    account_id: int,
    content: str | None,
    media: list[dict[str, Any]],
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """The set's composer, checked against the account: its channels and
    library files have to be the account's own."""
    channel_ids = [t["channel_id"] for t in targets]
    if len(set(channel_ids)) != len(channel_ids):
        raise svc._unprocessable("Un canal aparece dos veces")
    channels = await svc.channels_by_id(session, channel_ids=channel_ids)
    if any(
        cid not in channels or channels[cid].account_id != account_id
        for cid in channel_ids
    ):
        raise svc._unprocessable("El canal no existe o no pertenece a esta cuenta")

    asset_ids = [m["media_id"] for m in media if m.get("media_id") is not None]
    assets = await media_library.get_assets(
        session, account_id=account_id, asset_ids=asset_ids
    )
    clean_media: list[dict[str, Any]] = []
    for item in media:
        if item.get("media_id") is not None:
            if item["media_id"] not in assets:
                raise svc._unprocessable(
                    "Un archivo del set no está en la biblioteca de esta cuenta"
                )
            clean_media.append({"media_id": item["media_id"]})
        elif item.get("type") in MEDIA_TYPES and item.get("url"):
            clean_media.append({"type": item["type"], "url": item["url"]})
        else:
            raise svc._unprocessable(
                "Cada archivo del set necesita media_id, o type (image o video) y url"
            )
    return {
        "content": content,
        "media": clean_media,
        "targets": [
            {
                "channel_id": t["channel_id"],
                "settings": t.get("settings") or {},
                "content_override": t.get("content_override"),
            }
            for t in targets
        ],
    }


async def save_set(
    session: AsyncSession,
    *,
    publication_set: PublicationSet,
    values: dict[str, Any],
) -> PublicationSet:
    """Create or edit; ``values`` has only the fields being set."""
    if "name" in values and values["name"] is not None:
        name = values["name"].strip()
        if not name:
            raise svc._unprocessable("El set necesita un nombre")
        publication_set.name = name
    current = publication_set.payload or {}
    publication_set.payload = await _clean_payload(
        session,
        account_id=publication_set.account_id,
        content=values["content"] if "content" in values else current.get("content"),
        media=(
            values["media"]
            if values.get("media") is not None
            else current.get("media") or []
        ),
        targets=(
            values["targets"]
            if values.get("targets") is not None
            else current.get("targets") or []
        ),
    )
    session.add(publication_set)
    await session.flush()
    await session.refresh(publication_set)
    return publication_set


async def delete_set(session: AsyncSession, *, publication_set: PublicationSet) -> None:
    await session.delete(publication_set)
    await session.flush()


__all__ = [
    "delete_set",
    "delete_signature",
    "get_set",
    "get_signature",
    "list_sets",
    "list_signatures",
    "save_set",
    "save_signature",
]
