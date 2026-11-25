"""Import an Instagram account's past DMs when it connects.

Meta's Conversations API lists every thread of the account, but only
gives the content of the **20 most recent messages** of each one (older
messages answer "deleted"), and leaves out message requests idle for 30
days. So the import brings every conversation with its recent context.

Runs as a background job right after connecting (and on a reconnect,
which fills what arrived while disconnected). Everything lands quietly:
resolved conversations with their original dates, no bots, automations
or notifications. Already stored messages (same ``mid``) are skipped.

Facebook Login: ``GET /{page-id}/conversations?platform=instagram`` on
graph.facebook.com with the Page token. Instagram Login:
``GET /me/conversations?platform=instagram`` on graph.instagram.com.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import Message
from app.domains.conversations.service import quiet_conversation, store_imported_message
from app.domains.inboxes.models import CHANNEL_TYPE_INSTAGRAM, Inbox, InstagramChannel
from app.domains.instagram.graph import graph_base, graph_host, meta_error_text

log = logging.getLogger(__name__)

_TIMEOUT = 20.0
# Conversations per page, and pages at most (a very busy account keeps its
# most recent 1000 threads).
_PAGE_SIZE = 25
_MAX_PAGES = 40
# What Meta lets us read of each thread.
_MESSAGES_PER_THREAD = 20
_FIELDS = (
    "participants,updated_time,"
    f"messages.limit({_MESSAGES_PER_THREAD})"
    "{id,created_time,from,to,message,attachments}"
)
# Conversations API attachment keys -> the webhook's attachment ``type``.
_ATTACHMENT_KINDS = (("image_data", "image"), ("video_data", "video"))


class HistoryError(Exception):
    """Meta refused the listing (token, permission)."""


def _when(raw: Any) -> datetime:
    try:
        return datetime.fromisoformat(str(raw).replace("+0000", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def _webhook_attachments(message: dict[str, Any]) -> list[dict[str, Any]]:
    """The Conversations API shape, rewritten as the webhook's, so the
    same downloader stores the files."""
    out: list[dict[str, Any]] = []
    for item in (message.get("attachments") or {}).get("data") or []:
        if not isinstance(item, dict):
            continue
        for key, kind in _ATTACHMENT_KINDS:
            url = (item.get(key) or {}).get("url")
            if url:
                out.append({"type": kind, "payload": {"url": url}})
                break
        else:
            if item.get("file_url"):
                out.append({"type": "file", "payload": {"url": item["file_url"]}})
    return out


async def _threads(channel: InstagramChannel, *, page_id: str | None) -> list[dict[str, Any]]:
    """Every conversation Meta lists, newest first, with its recent messages."""
    url = f"{graph_base()}/{page_id or 'me'}/conversations"
    params: dict[str, Any] | None = {
        "platform": "instagram",
        "fields": _FIELDS,
        "limit": _PAGE_SIZE,
        "access_token": channel.access_token,
    }
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for _ in range(_MAX_PAGES):
            try:
                resp = await client.get(url, params=params)
            except httpx.HTTPError as exc:
                raise HistoryError(f"Meta no respondió: {type(exc).__name__}") from exc
            if resp.status_code >= 400:
                raise HistoryError(meta_error_text(resp))
            body = resp.json()
            out.extend(t for t in body.get("data") or [] if isinstance(t, dict))
            following = (body.get("paging") or {}).get("next")
            if not following:
                break
            # ``next`` already carries every parameter, the token included.
            url, params = str(following), None
    return out


async def _import_thread(
    session: AsyncSession,
    *,
    channel: InstagramChannel,
    inbox: Inbox,
    thread: dict[str, Any],
) -> int:
    from app.domains.instagram.incoming import (
        _build_ig_attachments,
        _placeholder_name,
        find_or_create_ig_contact,
    )

    ours = str(channel.instagram_id)
    people = [
        p
        for p in (thread.get("participants") or {}).get("data") or []
        if isinstance(p, dict) and str(p.get("id") or "") != ours
    ]
    if not people or not people[0].get("id"):
        return 0
    igsid = str(people[0]["id"])
    username = people[0].get("username")
    messages = [m for m in (thread.get("messages") or {}).get("data") or [] if isinstance(m, dict)]
    if not messages:
        return 0

    contact = await find_or_create_ig_contact(session, account_id=channel.account_id, igsid=igsid)
    if username and contact.name == _placeholder_name(igsid):
        contact.name = str(username)
        session.add(contact)
    contact_inbox = await ContactInboxBuilder(
        session=session, contact=contact, inbox=inbox, source_id=igsid
    ).perform()
    # Meta lists them newest first: the conversation is dated by the oldest.
    messages.sort(key=lambda m: str(m.get("created_time") or ""))
    conversation = await quiet_conversation(
        session, contact_inbox=contact_inbox, at=_when(messages[0].get("created_time"))
    )

    stored = 0
    for message in messages:
        mid = str(message.get("id") or "")
        if not mid:
            continue
        already = (
            await session.exec(
                select(Message.id).where(
                    Message.account_id == channel.account_id, Message.source_id == mid
                )
            )
        ).first()
        if already is not None:
            continue
        text = str(message.get("message") or "")
        attachments, fallback = await _build_ig_attachments(
            account_id=channel.account_id,
            message_block={"attachments": _webhook_attachments(message)},
            mid=mid,
        )
        if not text and not fallback and not attachments:
            continue  # A reaction, a deleted message, a story mention gone.
        sender = str((message.get("from") or {}).get("id") or "")
        if await store_imported_message(
            session,
            conversation=conversation,
            content=text or fallback,
            outgoing=sender == ours,
            source_id=mid,
            at=_when(message.get("created_time")),
            attachments=attachments or None,
        ):
            stored += 1
    return stored


async def import_history(session: AsyncSession, channel_instagram_id: int) -> dict[str, int]:
    """Import the channel's DMs. The caller commits."""
    from app.domains.instagram import connect_service, graph

    channel = await session.get(InstagramChannel, channel_instagram_id)
    if channel is None or channel.id is None or not channel.access_token:
        return {"conversations": 0, "messages": 0}
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_INSTAGRAM, Inbox.channel_id == channel.id
            )
        )
    ).first()
    if inbox is None:
        return {"conversations": 0, "messages": 0}
    setting = await connect_service.get_channel_setting(session, channel_instagram_id=channel.id)
    login_type = setting.login_type if setting else None
    # Facebook Login lists the Page's Instagram threads; without a Page id
    # (a hand-typed connection) there is nothing to ask for.
    page_id = setting.page_id if setting and login_type != "instagram" else None
    if login_type != "instagram" and not page_id:
        return {"conversations": 0, "messages": 0}

    with graph_host(graph.host_for_login_type(login_type)):
        threads = await _threads(channel, page_id=page_id)
        conversations = messages = 0
        for thread in threads:
            try:
                async with session.begin_nested():
                    count = await _import_thread(
                        session, channel=channel, inbox=inbox, thread=thread
                    )
            except Exception:  # one bad thread must not lose the rest
                log.exception(
                    "instagram.history.thread_failed channel_id=%s thread=%s",
                    channel.id,
                    thread.get("id"),
                )
                continue
            if count:
                conversations += 1
                messages += count
    log.info(
        "instagram.history.imported channel_id=%s threads=%s conversations=%s messages=%s",
        channel.id,
        len(threads),
        conversations,
        messages,
    )
    return {"conversations": conversations, "messages": messages}


async def enqueue_import(channel_instagram_id: int) -> None:
    """Import the history shortly, off the request (after it commits).
    Best-effort: without a worker the account still connects."""
    settings = get_settings()
    if settings.app_env == "test":
        return
    from arq import create_pool
    from arq.connections import RedisSettings

    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.arq_redis_url))
        try:
            await pool.enqueue_job(
                "import_instagram_history_task",
                channel_instagram_id,
                _job_id=f"instagram-history-{channel_instagram_id}",
                _defer_by=5,
            )
        finally:
            await pool.aclose()
    except Exception as exc:  # noqa: BLE001 - optional side job, never fail the connection
        log.warning(
            "instagram.history.enqueue_failed channel_id=%s err=%s",
            channel_instagram_id,
            type(exc).__name__,
        )


__all__ = ["HistoryError", "enqueue_import", "import_history"]
