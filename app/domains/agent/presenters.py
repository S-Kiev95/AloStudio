"""JSON shapes of the agent chat (contract in ``PLAN.agent-chat.md``)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import AccountContext
from app.core.i18n import t, user_locale
from app.domains.agent.models import (
    AGENT_ROLE_ASSISTANT,
    AGENT_ROLE_USER,
    TOOL_STATUS_DONE,
    TOOL_STATUS_ERROR,
    TOOL_STATUS_INVALID,
    TOOL_STATUS_PENDING,
    TOOL_STATUS_REJECTED,
    AgentMessage,
    AgentThread,
)
from app.domains.agent.service import PUBLICATION_TOOLS, is_read_tool
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.conversations.permission import can_view_conversation, can_view_inbox
from app.domains.inboxes.models import Inbox
from app.domains.macros.models import Macro
from app.domains.media_library import service as media_svc
from app.domains.publishing import service as publishing_svc
from app.domains.teams.models import Team
from app.domains.users.models import AccountUser, User

# Tools with their own words for what the agent did
# (``agent.tool.<name>.done`` / ``.failed``); the rest say read or done.
_LABELLED_TOOLS: frozenset[str] = frozenset(
    {
        "list_publication_channels",
        "list_media",
        "list_publications",
        "get_publishing_analytics",
        "create_publication",
        "cancel_publication",
    }
)
# The publications have their own card; any other write shows its
# arguments, with these names (``agent.args.<key>``) and ids as names.
_ARGUMENT_KEYS: frozenset[str] = frozenset(
    {
        "conversation_id",
        "conversation_ids",
        "macro_id",
        "contact_id",
        "inbox_id",
        "team_id",
        "assignee_id",
        "agent_id",
        "owner_id",
        "content",
        "message",
        "private",
        "status",
        "priority",
        "labels",
        "name",
        "title",
        "description",
        "notes",
        "email",
        "phone_number",
        "value",
        "currency",
        "starts_at",
        "ends_at",
        "due_at",
        "scheduled_at",
        "product_id",
        "product_ids",
        "stage_id",
        "active",
        "enabled",
    }
)
_USER_KEYS: frozenset[str] = frozenset({"assignee_id", "agent_id", "owner_id"})
_VALUE_LIMIT = 2000


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def present_thread_summary(thread: AgentThread, *, has_pending_action: bool) -> dict[str, Any]:
    return {
        "id": thread.id,
        "title": thread.title,
        "updated_at": _iso(thread.updated_at),
        "has_pending_action": has_pending_action,
    }


async def present_thread(
    session: AsyncSession,
    ctx: AccountContext,
    thread: AgentThread,
    rows: list[AgentMessage],
) -> dict[str, Any]:
    pending = next((r for r in rows if r.status == TOOL_STATUS_PENDING), None)
    locale = user_locale(ctx.user)
    reads = {r.tool_name for r in rows if r.tool_name and await is_read_tool(r.tool_name)}
    return {
        "id": thread.id,
        "title": thread.title,
        "created_at": _iso(thread.created_at),
        "updated_at": _iso(thread.updated_at),
        "items": [
            item
            for item in (_present_item(r, locale=locale, reads=reads) for r in rows)
            if item is not None
        ],
        "pending_action": (
            await _present_pending(session, ctx, pending) if pending is not None else None
        ),
    }


def _present_item(row: AgentMessage, *, locale: str, reads: set[str]) -> dict[str, Any] | None:
    if row.role in (AGENT_ROLE_USER, AGENT_ROLE_ASSISTANT):
        if not (row.content or "").strip():
            return None  # an assistant step that only called a tool
        return {
            "id": row.id,
            "kind": row.role,
            "content": row.content,
            "created_at": _iso(row.created_at),
        }
    result = _load(row.content)
    name = row.tool_name or ""
    if name in _LABELLED_TOOLS:
        done_label = t(locale, f"agent.tool.{name}.done")
        error_label = t(locale, f"agent.tool.{name}.failed")
    else:
        done_label = t(locale, "agent.tool.read_done" if name in reads else "agent.tool.write_done")
        error_label = t(locale, "agent.tool.failed")
    status, label, detail = {
        TOOL_STATUS_PENDING: ("pending", t(locale, "agent.status.pending"), None),
        TOOL_STATUS_DONE: ("done", done_label, None),
        TOOL_STATUS_ERROR: ("error", error_label, result.get("error")),
        TOOL_STATUS_INVALID: ("error", t(locale, "agent.status.invalid"), result.get("error")),
        TOOL_STATUS_REJECTED: ("rejected", t(locale, "agent.status.rejected"), None),
    }.get(row.status or "", ("error", error_label, result.get("error")))
    publication_id = result.get("id") if name == "create_publication" and status == "done" else None
    return {
        "id": row.id,
        "kind": "tool",
        "tool": name,
        "status": status,
        "label": label,
        "detail": detail if isinstance(detail, str) else None,
        "publication_id": publication_id if isinstance(publication_id, int) else None,
        "created_at": _iso(row.created_at),
    }


def _load(content: str | None) -> dict[str, Any]:
    try:
        value = json.loads(content or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _parse_datetime(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


async def _present_pending(
    session: AsyncSession, ctx: AccountContext, row: AgentMessage
) -> dict[str, Any]:
    """The proposal as the confirmation card shows it: built from the very
    arguments that run on confirm."""
    arguments = row.tool_arguments or {}
    if row.tool_name not in PUBLICATION_TOOLS:
        return await _present_generic_pending(session, ctx, row)
    locale = user_locale(ctx.user)
    if row.tool_name == "cancel_publication":
        publication = await _existing_publication(session, ctx, arguments.get("publication_id"))
        return {
            "id": row.tool_call_id,
            "tool": "cancel_publication",
            "title": t(locale, "agent.pending.cancel_publication.title"),
            "confirm_label": t(locale, "agent.pending.cancel_publication.confirm"),
            "publication": publication,
        }
    scheduled_for = _parse_datetime(arguments.get("scheduled_for"))
    content = arguments.get("content")
    return {
        "id": row.tool_call_id,
        "tool": "create_publication",
        "title": t(locale, "agent.pending.create_publication.title"),
        "confirm_label": t(
            locale,
            "agent.pending.create_publication.confirm"
            if scheduled_for is not None
            else "agent.pending.create_publication.confirm_now",
        ),
        "publication": {
            "id": None,
            "content": content if isinstance(content, str) else None,
            "scheduled_for": _iso(scheduled_for.astimezone(UTC)) if scheduled_for else None,
            "channels": await _channels(session, ctx, arguments.get("channel_ids")),
            "media": await _media(session, ctx, arguments.get("media")),
        },
    }


def _ids(raw: Any) -> list[int]:
    # ``bool`` is an ``int`` in Python: ``true`` must not mean id 1.
    if not isinstance(raw, list):
        return []
    return [v for v in raw if isinstance(v, int) and not isinstance(v, bool)]


async def _channels(
    session: AsyncSession, ctx: AccountContext, raw: Any
) -> list[dict[str, Any]]:
    ids = _ids(raw)
    channels = await publishing_svc.channels_by_id(session, channel_ids=ids)
    return [
        {"id": channel.id, "name": channel.name, "network": channel.network}
        for channel in (channels.get(i) for i in ids)
        if channel is not None and channel.account_id == ctx.account.id
    ]


async def _media(session: AsyncSession, ctx: AccountContext, raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items = [item for item in raw if isinstance(item, dict)]
    assets = await media_svc.get_assets(
        session,
        account_id=ctx.account.id,  # type: ignore[arg-type]
        asset_ids=_ids([item.get("media_id") for item in items]),
    )
    media: list[dict[str, Any]] = []
    for item in items:
        asset = assets.get(item.get("media_id"))  # type: ignore[arg-type]
        if asset is not None:
            media.append(
                {"id": asset.id, "type": asset.kind, "url": media_svc.asset_preview_url(asset)}
            )
        elif isinstance(item.get("url"), str):
            media.append({"id": None, "type": item.get("type"), "url": item["url"]})
    return media


async def _existing_publication(
    session: AsyncSession, ctx: AccountContext, publication_id: Any
) -> dict[str, Any]:
    """The publication to cancel. Gone since it was proposed (deleted from
    the calendar meanwhile), only its id is left: confirming then fails."""
    valid_id = isinstance(publication_id, int) and not isinstance(publication_id, bool)
    publication = (
        await publishing_svc.get_publication(
            session,
            account_id=ctx.account.id,  # type: ignore[arg-type]
            publication_id=publication_id,
        )
        if valid_id
        else None
    )
    if publication is None:
        return {
            "id": publication_id if valid_id else None,
            "content": None,
            "scheduled_for": None,
            "channels": [],
            "media": [],
        }
    targets = (
        await publishing_svc.targets_by_publication(session, publication_ids=[publication_id])
    ).get(publication_id, [])
    return {
        "id": publication.id,
        "content": publication.content,
        "scheduled_for": _iso(publication.scheduled_for),
        "channels": await _channels(session, ctx, [t.channel_id for t in targets]),
        "media": await _media(session, ctx, publication.media or []),
    }


async def _present_generic_pending(
    session: AsyncSession, ctx: AccountContext, row: AgentMessage
) -> dict[str, Any]:
    """Any other write: its arguments, named and with ids shown as names,
    exactly as they run on confirm."""
    locale = user_locale(ctx.user)
    details = [
        {
            "label": t(locale, f"agent.args.{key}") if key in _ARGUMENT_KEYS else key,
            "value": await _argument_value(session, ctx, key, value, locale),
        }
        for key, value in (row.tool_arguments or {}).items()
        if value is not None
    ]
    return {
        "id": row.tool_call_id,
        "tool": row.tool_name,
        "title": t(locale, "agent.pending.title"),
        "confirm_label": t(locale, "agent.pending.confirm"),
        "publication": None,
        "details": details,
    }


async def _argument_value(
    session: AsyncSession, ctx: AccountContext, key: str, value: Any, locale: str
) -> str:
    if isinstance(value, bool):
        return t(locale, "agent.yes" if value else "agent.no")
    if isinstance(value, int) and not isinstance(value, bool):
        name = await _name_of(session, ctx, key, value)
        if name:
            return name
    if isinstance(value, list) and key == "conversation_ids":
        names = [
            (await _name_of(session, ctx, "conversation_id", v) if isinstance(v, int) else None)
            or str(v)
            for v in value
        ]
        return ", ".join(names)[:_VALUE_LIMIT]
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)[:_VALUE_LIMIT]
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)[:_VALUE_LIMIT]
    return str(value)[:_VALUE_LIMIT]


async def _name_of(session: AsyncSession, ctx: AccountContext, key: str, row_id: int) -> str | None:
    """What an id stands for, only from this account (and, for a
    conversation, only if the user can see it)."""
    account_id = ctx.account.id
    if key == "conversation_id":
        conversation = await session.get(Conversation, row_id)
        if conversation is None or conversation.account_id != account_id:
            return None
        if not await can_view_conversation(
            session,
            account_id=account_id,  # type: ignore[arg-type]
            user_id=ctx.user.id,  # type: ignore[arg-type]
            conversation=conversation,
        ):
            return None
        contact = await session.get(Contact, conversation.contact_id)
        who = (contact.name or contact.phone_number or contact.email) if contact else None
        return f"#{conversation.display_id} · {who}" if who else f"#{conversation.display_id}"
    if key == "contact_id":
        contact = await session.get(Contact, row_id)
        if contact is None or contact.account_id != account_id:
            return None
        return contact.name or contact.phone_number or contact.email
    if key == "inbox_id":
        inbox = await session.get(Inbox, row_id)
        if inbox is None or inbox.account_id != account_id:
            return None
        if not await can_view_inbox(
            session,
            account_id=account_id,  # type: ignore[arg-type]
            user_id=ctx.user.id,  # type: ignore[arg-type]
            inbox_id=row_id,
        ):
            return None
        return inbox.name
    if key == "macro_id":
        macro = await session.get(Macro, row_id)
        return macro.name if macro is not None and macro.account_id == account_id else None
    if key == "team_id":
        team = await session.get(Team, row_id)
        return team.name if team is not None and team.account_id == account_id else None
    if key in _USER_KEYS:
        member = (
            await session.exec(
                select(User.name)
                .join(AccountUser, AccountUser.user_id == User.id)  # type: ignore[arg-type]
                .where(AccountUser.account_id == account_id, User.id == row_id)
            )
        ).first()
        return member or None
    return None


__all__ = ["present_thread", "present_thread_summary"]
