"""Auto post — new entries of an RSS / Atom feed become publications.

A scheduled job reads each active feed, takes the entries above the newest
one already seen and turns each into a publication: its title and link as
the text and its image, when it has one. The entry goes only to the
channels that accept it (an entry without an image can't go to Instagram),
published right away or saved as a draft for someone to review.

Feeds are URLs somebody typed, so they are fetched with
:func:`app.core.outbound.guarded_client` (no private addresses, redirects
included) and capped in size. They are parsed with the standard library
(RSS 2.0, Atom and the Media RSS image tags).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import httpx
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.outbound import guarded_client
from app.domains.publishing import service as svc
from app.domains.publishing.adapters import adapter_for_network
from app.domains.publishing.models import (
    AUTOPOST_MODE_DRAFT,
    AUTOPOST_MODES,
    CHANNEL_STATUS_ACTIVE,
    Publication,
    PublicationTarget,
    PublishingAutopost,
)

log = logging.getLogger(__name__)

FEED_MAX_BYTES = 2 * 1024 * 1024
# At most this many entries per feed and run, oldest first; a burst above
# it (a feed that republished its whole archive) keeps only the newest.
MAX_PER_RUN = 5
PREVIEW_ITEMS = 5

_ATOM = "{http://www.w3.org/2005/Atom}"
_MEDIA = "{http://search.yahoo.com/mrss/}"


class FeedError(Exception):
    """A feed that can't be read; the message is for the owner."""


@dataclass
class FeedItem:
    key: str
    title: str
    link: str | None
    image_url: str | None
    published_at: datetime | None


# ---------------------------------------------------------------------------
# Reading feeds
# ---------------------------------------------------------------------------
def _text(element: ElementTree.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)  # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))  # Atom
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _media_image(item: ElementTree.Element) -> str | None:
    for tag in (f"{_MEDIA}content", f"{_MEDIA}thumbnail"):
        for media in item.iter(tag):
            url = media.get("url")
            kind = (media.get("medium") or media.get("type") or "image").lower()
            if url and (kind == "image" or kind.startswith("image/") or tag.endswith("thumbnail")):
                return url
    return None


def parse_feed(raw: bytes) -> list[FeedItem]:
    """Entries of an RSS 2.0 or Atom document, newest first."""
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise FeedError("La URL no devolvió un feed RSS o Atom válido.") from exc

    items: list[FeedItem] = []
    if root.tag == f"{_ATOM}feed":
        for entry in root.findall(f"{_ATOM}entry"):
            link = None
            image = None
            for node in entry.findall(f"{_ATOM}link"):
                rel = node.get("rel") or "alternate"
                if rel == "alternate" and link is None:
                    link = node.get("href")
                elif rel == "enclosure" and (node.get("type") or "").startswith("image/"):
                    image = node.get("href")
            key = _text(entry.find(f"{_ATOM}id")) or link or _text(entry.find(f"{_ATOM}title"))
            if not key:
                continue
            items.append(
                FeedItem(
                    key=key,
                    title=_text(entry.find(f"{_ATOM}title")),
                    link=link,
                    image_url=image or _media_image(entry),
                    published_at=_date(
                        _text(entry.find(f"{_ATOM}published"))
                        or _text(entry.find(f"{_ATOM}updated"))
                    ),
                )
            )
    else:
        channel = root.find("channel")
        if channel is None:
            raise FeedError("La URL no devolvió un feed RSS o Atom válido.")
        for entry in channel.findall("item"):
            link = _text(entry.find("link")) or None
            enclosure = entry.find("enclosure")
            image = (
                enclosure.get("url")
                if enclosure is not None and (enclosure.get("type") or "").startswith("image/")
                else None
            )
            key = _text(entry.find("guid")) or link or _text(entry.find("title"))
            if not key:
                continue
            items.append(
                FeedItem(
                    key=key,
                    title=_text(entry.find("title")),
                    link=link,
                    image_url=image or _media_image(entry),
                    published_at=_date(_text(entry.find("pubDate"))),
                )
            )
    # Most feeds list newest first; order by date when every entry has one.
    if items and all(i.published_at for i in items):
        items.sort(key=lambda i: i.published_at, reverse=True)  # type: ignore[arg-type,return-value]
    return items


async def fetch_feed(url: str) -> list[FeedItem]:
    """Read and parse a feed. Raises :class:`FeedError`."""
    try:
        async with (
            guarded_client(timeout=20.0, follow_redirects=True) as client,
            client.stream(
                "GET", url, headers={"User-Agent": "AloStudio/1.0 (+auto post)"}
            ) as resp,
        ):
            if resp.status_code >= 400:
                raise FeedError(f"El feed respondió con un error ({resp.status_code}).")
            body = bytearray()
            async for chunk in resp.aiter_bytes():
                body.extend(chunk)
                if len(body) > FEED_MAX_BYTES:
                    raise FeedError("El feed es demasiado grande (más de 2 MB).")
    except httpx.HTTPError as exc:
        raise FeedError("No se pudo leer el feed: revisá la URL.") from exc
    return parse_feed(bytes(body))


# ---------------------------------------------------------------------------
# Publishing new entries
# ---------------------------------------------------------------------------
def _content(item: FeedItem) -> str:
    return "\n\n".join(part for part in (item.title, item.link) if part)


async def _targets_for(
    session: AsyncSession, autopost: PublishingAutopost, item: FeedItem
) -> list[dict[str, Any]]:
    """The autopost's channels that accept this entry as it is."""
    channels = await svc.list_channels(session, account_id=autopost.account_id)
    wanted = set(autopost.channel_ids or [])
    media = [{"type": "image", "url": item.image_url}] if item.image_url else []
    probe = Publication(account_id=autopost.account_id, content=_content(item), media=media)
    targets = []
    for channel in channels:
        if channel.status != CHANNEL_STATUS_ACTIVE or (wanted and channel.id not in wanted):
            continue
        adapter = adapter_for_network(channel.network)
        target = PublicationTarget(
            account_id=autopost.account_id,
            channel_id=channel.id,  # type: ignore[arg-type]
            network=channel.network,
            settings={},
        )
        if adapter is not None and not adapter.validate(probe, target):
            targets.append({"channel_id": channel.id})
    return targets


async def _publish(
    session: AsyncSession, autopost: PublishingAutopost, item: FeedItem
) -> bool:
    targets = await _targets_for(session, autopost, item)
    if not targets:
        autopost.last_error = (
            f"«{item.title or item.link}» no se publicó: ningún canal la acepta así "
            "(por ejemplo, Instagram necesita una imagen)."
        )
        return False
    await svc.create_publication(
        session,
        account_id=autopost.account_id,
        created_by_id=autopost.created_by_id,
        payload={
            "content": _content(item),
            "media": [{"type": "image", "url": item.image_url}] if item.image_url else [],
            # Without a date it goes out on the next scheduler tick.
            "draft": autopost.mode == AUTOPOST_MODE_DRAFT,
            "targets": targets,
        },
    )
    return True


async def sync_autopost(
    session: AsyncSession, autopost: PublishingAutopost, *, now: datetime | None = None
) -> int:
    """Read the feed and publish its new entries. Returns how many became
    publications; a feed that fails is recorded in ``last_error``."""
    autopost.last_checked_at = now or datetime.now(UTC)
    try:
        items = await fetch_feed(autopost.feed_url)
    except FeedError as exc:
        autopost.last_error = str(exc)
        session.add(autopost)
        return 0
    autopost.last_error = None
    if not items:
        session.add(autopost)
        return 0

    keys = [i.key for i in items]
    if autopost.last_item_key is None:
        new = items[:1] if autopost.start_with_latest else []
    elif autopost.last_item_key in keys:
        new = items[: keys.index(autopost.last_item_key)]
    else:
        # The last entry seen fell off the feed: only the newest is surely new.
        new = items[:1]

    published = 0
    for item in reversed(new[:MAX_PER_RUN]):
        published += int(await _publish(session, autopost, item))
    autopost.last_item_key = items[0].key
    session.add(autopost)
    return published


async def sync_all(session: AsyncSession) -> int:
    """Every active autopost, each committed on its own."""
    ids = (
        await session.exec(
            select(PublishingAutopost.id)
            .where(col(PublishingAutopost.active).is_(True))
            .order_by(col(PublishingAutopost.id))
        )
    ).all()
    total = 0
    for autopost_id in ids:
        try:
            autopost = await session.get(PublishingAutopost, autopost_id)
            if autopost is not None:
                total += await sync_autopost(session, autopost)
            await session.commit()
        except Exception:
            # One feed must not sink the rest.
            await session.rollback()
            log.exception("publishing.autopost.failed autopost_id=%s", autopost_id)
    return total


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def list_autoposts(
    session: AsyncSession, *, account_id: int
) -> list[PublishingAutopost]:
    return list(
        (
            await session.exec(
                select(PublishingAutopost)
                .where(PublishingAutopost.account_id == account_id)
                .order_by(col(PublishingAutopost.id))
            )
        ).all()
    )


async def get_autopost(
    session: AsyncSession, *, account_id: int, autopost_id: int
) -> PublishingAutopost | None:
    autopost = await session.get(PublishingAutopost, autopost_id)
    if autopost is None or autopost.account_id != account_id:
        return None
    return autopost


async def save_autopost(
    session: AsyncSession, *, autopost: PublishingAutopost, values: dict[str, Any]
) -> PublishingAutopost:
    """Create or edit; ``values`` has only the fields being set. A new or
    changed feed URL is read once, so a wrong one is refused here."""
    if values.get("name") is not None:
        name = values["name"].strip()
        if not name:
            raise svc._unprocessable("El auto post necesita un nombre")
        autopost.name = name
    if values.get("mode") is not None:
        if values["mode"] not in AUTOPOST_MODES:
            raise svc._unprocessable("mode tiene que ser publish o draft")
        autopost.mode = values["mode"]
    for field in ("active", "start_with_latest"):
        if values.get(field) is not None:
            setattr(autopost, field, values[field])
    if values.get("channel_ids") is not None:
        channel_ids = list(dict.fromkeys(values["channel_ids"]))
        channels = await svc.channels_by_id(session, channel_ids=channel_ids)
        if any(
            cid not in channels or channels[cid].account_id != autopost.account_id
            for cid in channel_ids
        ):
            raise svc._unprocessable("El canal no existe o no pertenece a esta cuenta")
        autopost.channel_ids = channel_ids
    feed_url = (values.get("feed_url") or "").strip()
    if feed_url and feed_url != autopost.feed_url:
        try:
            await fetch_feed(feed_url)
        except FeedError as exc:
            raise svc._unprocessable(str(exc)) from exc
        autopost.feed_url = feed_url
        autopost.last_item_key = None
        autopost.last_error = None
    if not autopost.feed_url:
        raise svc._unprocessable("El auto post necesita la URL del feed")
    session.add(autopost)
    await session.flush()
    await session.refresh(autopost)
    return autopost


async def delete_autopost(session: AsyncSession, *, autopost: PublishingAutopost) -> None:
    await session.delete(autopost)
    await session.flush()


async def preview_feed(url: str) -> list[FeedItem]:
    """The feed's newest entries, to check it before saving."""
    try:
        return (await fetch_feed(url))[:PREVIEW_ITEMS]
    except FeedError as exc:
        raise svc._unprocessable(str(exc)) from exc


__all__ = [
    "FeedError",
    "FeedItem",
    "delete_autopost",
    "fetch_feed",
    "get_autopost",
    "list_autoposts",
    "parse_feed",
    "preview_feed",
    "save_autopost",
    "sync_all",
    "sync_autopost",
]
