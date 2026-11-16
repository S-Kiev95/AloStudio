"""Contact profile pictures (F14).

Only Instagram and Messenger give one: the Graph API returns ``profile_pic``
for someone who wrote to the Page or account. WhatsApp's Cloud API doesn't,
so those contacts keep their initials.

Meta's link expires within days, so the picture is downloaded into our
object store under a fixed key per contact and served through
``GET /contacts/{id}/avatar``. It is fetched shortly after a contact's first
message (a deferred job, so the webhook isn't slowed down) and refreshed by
a daily job for contacts still active, in case they changed it.

Everything here is best-effort: a picture that fails to load leaves the
initials, never an error.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.outbound import guarded_client
from app.core.storage import object_url, presigned_put_url
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.inboxes.models import (
    CHANNEL_TYPE_FACEBOOK,
    CHANNEL_TYPE_INSTAGRAM,
    FacebookPage,
    Inbox,
    InstagramChannel,
)

log = logging.getLogger(__name__)

# Meta's pictures are small; anything bigger isn't a profile picture.
MAX_BYTES = 2 * 1024 * 1024
# Asked again after this long, for contacts that wrote recently.
REFRESH_AFTER = timedelta(days=7)
ACTIVE_WITHIN = timedelta(days=30)
# Per daily run, so a large backlog never hammers Meta's rate limit.
REFRESH_BATCH = 200
# The job runs after the webhook's transaction has committed the contact.
FIRST_FETCH_DELAY_SECONDS = 15

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def avatar_key(contact: Contact) -> str:
    return f"accounts/{contact.account_id}/contacts/{contact.id}/avatar"


def contact_thumbnail(contact: Contact) -> str:
    """The browser URL of the contact's picture, or ``""`` without one.

    Through the authenticated proxy, like attachments: the object store is
    internal. ``v`` changes with each refresh so the browser can cache it.
    """
    if not contact.avatar_url or contact.id is None:
        return ""
    version = (
        int(contact.avatar_refreshed_at.timestamp())
        if contact.avatar_refreshed_at
        else 0
    )
    return (
        f"/api/backend/api/v1/accounts/{contact.account_id}"
        f"/contacts/{contact.id}/avatar?v={version}"
    )


def needs_first_fetch(contact: Contact) -> bool:
    return contact.avatar_refreshed_at is None and not is_manual(contact)


# A picture uploaded (or removed) by hand: Meta's never replaces it.
MANUAL_FLAG = "avatar_manual"
UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def is_manual(contact: Contact) -> bool:
    return bool((contact.additional_attributes or {}).get(MANUAL_FLAG))


def _mark_manual(contact: Contact) -> None:
    # A new dict, so SQLAlchemy sees the JSONB change.
    contact.additional_attributes = {**(contact.additional_attributes or {}), MANUAL_FLAG: True}


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------
async def _profile_pic_url(*, user_id: str, access_token: str) -> str | None:
    """Meta's (short-lived) link to the picture, or ``None``."""
    from app.domains.instagram.graph import graph_base

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{graph_base()}/{user_id}",
                params={"fields": "profile_pic", "access_token": access_token},
            )
        data = resp.json() if resp.status_code < 400 else {}
    except (httpx.HTTPError, ValueError):
        return None
    url = data.get("profile_pic")
    return url if isinstance(url, str) and url.startswith("https://") else None


async def _meta_identity(
    session: AsyncSession, contact: Contact
) -> tuple[str, str, Any] | None:
    """``(user_id, access_token, instagram_channel_or_None)`` from the
    contact's Instagram or Messenger inbox, Instagram first."""
    rows = (
        await session.exec(
            select(ContactInbox, Inbox)
            .join(Inbox, Inbox.id == ContactInbox.inbox_id)
            .where(
                ContactInbox.contact_id == contact.id,
                Inbox.channel_type.in_(  # type: ignore[attr-defined]
                    [CHANNEL_TYPE_INSTAGRAM, CHANNEL_TYPE_FACEBOOK]
                ),
            )
        )
    ).all()
    rows = sorted(rows, key=lambda r: r[1].channel_type != CHANNEL_TYPE_INSTAGRAM)
    for contact_inbox, inbox in rows:
        if inbox.channel_type == CHANNEL_TYPE_INSTAGRAM:
            ig = await session.get(InstagramChannel, inbox.channel_id)
            if ig is not None and ig.access_token:
                return contact_inbox.source_id, ig.access_token, ig
        else:
            page = await session.get(FacebookPage, inbox.channel_id)
            if page is not None and page.page_access_token:
                return contact_inbox.source_id, page.page_access_token, None
    return None


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
async def _download(url: str) -> tuple[bytes, str] | None:
    try:
        # Guarded: the URL comes from Meta's answer, still an outside value.
        async with guarded_client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except (httpx.HTTPError, ValueError) as exc:
        # Class name only: a signed CDN URL must not end up in the logs.
        log.warning("contacts.avatar.download_failed err=%s", type(exc).__name__)
        return None
    mime = (resp.headers.get("content-type") or "").split(";")[0].strip()
    if not mime.startswith("image/") or len(resp.content) > MAX_BYTES:
        log.warning("contacts.avatar.rejected mime=%s bytes=%s", mime, len(resp.content))
        return None
    return resp.content, mime


async def _put(key: str, data: bytes, mime: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            put = await client.put(
                presigned_put_url(key, expires=300),
                content=data,
                headers={"Content-Type": mime},
            )
            put.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("contacts.avatar.store_failed err=%s", type(exc).__name__)
        return False
    return True


async def refresh_avatar(session: AsyncSession, contact: Contact) -> bool:
    """Ask Meta for the contact's picture and keep our copy up to date.

    Returns whether a picture was stored. Marks the attempt either way, so a
    contact without a picture (or whose channel Meta won't answer for) isn't
    asked again until the next refresh window. The caller commits.
    """
    if is_manual(contact):
        # Marked as checked, so the daily batch doesn't keep picking it up.
        contact.avatar_refreshed_at = datetime.now(UTC)
        session.add(contact)
        await session.flush()
        return False
    identity = await _meta_identity(session, contact)
    if identity is None:
        return False
    user_id, token, ig_channel = identity

    if ig_channel is not None:
        from app.domains.instagram.graph import graph_host
        from app.domains.instagram.publishing_service import (
            _graph_host_for_channel,
        )

        with graph_host(await _graph_host_for_channel(session, ig_channel)):
            pic = await _profile_pic_url(user_id=user_id, access_token=token)
    else:
        pic = await _profile_pic_url(user_id=user_id, access_token=token)

    stored = False
    if pic is not None:
        downloaded = await _download(pic)
        if downloaded is not None:
            key = avatar_key(contact)
            stored = await _put(key, *downloaded)
            if stored:
                contact.avatar_url = object_url(key)

    contact.avatar_refreshed_at = datetime.now(UTC)
    session.add(contact)
    await session.flush()
    log.info("contacts.avatar.refreshed contact_id=%s stored=%s", contact.id, stored)
    return stored


async def store_uploaded_avatar(
    session: AsyncSession, contact: Contact, *, data: bytes, mime: str | None
) -> None:
    """Keep a picture someone uploaded from the panel. Raises ``ValueError``
    (``"avatar_type"`` / ``"avatar_size"`` / ``"avatar_store"``)."""
    mime = (mime or "").split(";")[0].strip().lower()
    if mime not in UPLOAD_TYPES:
        raise ValueError("avatar_type")
    if not data or len(data) > MAX_BYTES:
        raise ValueError("avatar_size")
    key = avatar_key(contact)
    if not await _put(key, data, mime):
        raise ValueError("avatar_store")
    contact.avatar_url = object_url(key)
    contact.avatar_refreshed_at = datetime.now(UTC)
    _mark_manual(contact)
    session.add(contact)
    await session.flush()


async def remove_avatar(session: AsyncSession, contact: Contact) -> None:
    """Drop the picture; Meta's isn't fetched back."""
    contact.avatar_url = None
    contact.avatar_refreshed_at = datetime.now(UTC)
    _mark_manual(contact)
    session.add(contact)
    await session.flush()


async def read_avatar(contact: Contact) -> tuple[bytes, str] | None:
    """Our stored copy, for the proxy route."""
    from app.core.storage import signed_read_url

    if not contact.avatar_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(signed_read_url(contact.avatar_url))
            resp.raise_for_status()
    except httpx.HTTPError:
        return None
    return resp.content, resp.headers.get("content-type") or "image/jpeg"


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
async def enqueue_first_fetch(contact: Contact) -> None:
    """Fetch a new contact's picture shortly, off the webhook's path.

    Best-effort and never raises: without a worker (tests, dev) the daily
    job picks the contact up later.
    """
    if contact.id is None or not needs_first_fetch(contact):
        return
    settings = get_settings()
    # Tests share the dev Redis: a job queued from a test contact would run
    # in the dev worker against another database.
    if settings.app_env == "test":
        return
    from arq import create_pool
    from arq.connections import RedisSettings

    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.arq_redis_url))
        try:
            await pool.enqueue_job(
                "refresh_contact_avatar_task",
                contact.id,
                _job_id=f"contact-avatar-{contact.id}",
                _defer_by=FIRST_FETCH_DELAY_SECONDS,
            )
        finally:
            await pool.aclose()
    except Exception as exc:  # noqa: BLE001 - optional side job, never fail the webhook
        log.warning(
            "contacts.avatar.enqueue_failed contact_id=%s err=%s",
            contact.id,
            type(exc).__name__,
        )


async def stale_contact_ids(
    session: AsyncSession, *, now: datetime | None = None
) -> list[int]:
    """Instagram and Messenger contacts active lately whose picture is
    missing or older than the refresh window."""
    now = now or datetime.now(UTC)
    rows = await session.exec(
        select(Contact.id)
        .join(ContactInbox, ContactInbox.contact_id == Contact.id)
        .join(Inbox, Inbox.id == ContactInbox.inbox_id)
        .where(
            Inbox.channel_type.in_(  # type: ignore[attr-defined]
                [CHANNEL_TYPE_INSTAGRAM, CHANNEL_TYPE_FACEBOOK]
            ),
            Contact.last_activity_at >= now - ACTIVE_WITHIN,  # type: ignore[operator]
            or_(
                Contact.avatar_refreshed_at.is_(None),  # type: ignore[union-attr]
                Contact.avatar_refreshed_at < now - REFRESH_AFTER,  # type: ignore[operator]
            ),
        )
        .distinct()
        .limit(REFRESH_BATCH)
    )
    return [cid for cid in rows.all() if cid is not None]


__all__ = [
    "contact_thumbnail",
    "enqueue_first_fetch",
    "read_avatar",
    "refresh_avatar",
    "remove_avatar",
    "stale_contact_ids",
    "store_uploaded_avatar",
]
