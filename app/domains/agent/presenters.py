"""JSON shapes of the agent chat (contract in ``PLAN.agent-chat.md``)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.deps import AccountContext
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
from app.domains.media_library import service as media_svc
from app.domains.publishing import service as publishing_svc

# What the agent did, for the user: (done, failed).
_TOOL_LABELS: dict[str, tuple[str, str]] = {
    "list_publication_channels": ("Consultó tus canales", "No pudo consultar tus canales"),
    "list_media": ("Revisó tu biblioteca de medios", "No pudo revisar la biblioteca de medios"),
    "list_publications": ("Revisó tu calendario", "No pudo revisar el calendario"),
    "get_publishing_analytics": ("Consultó las estadísticas", "No pudo consultar las estadísticas"),
    "create_publication": ("Programó la publicación", "No se pudo programar la publicación"),
    "cancel_publication": ("Borró la publicación", "No se pudo borrar la publicación"),
}
_FALLBACK_LABELS = ("Usó una herramienta", "No pudo usar una herramienta")


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
    return {
        "id": thread.id,
        "title": thread.title,
        "created_at": _iso(thread.created_at),
        "updated_at": _iso(thread.updated_at),
        "items": [item for item in (_present_item(r) for r in rows) if item is not None],
        "pending_action": (
            await _present_pending(session, ctx, pending) if pending is not None else None
        ),
    }


def _present_item(row: AgentMessage) -> dict[str, Any] | None:
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
    done_label, error_label = _TOOL_LABELS.get(name, _FALLBACK_LABELS)
    status, label, detail = {
        TOOL_STATUS_PENDING: ("pending", "Espera tu confirmación", None),
        TOOL_STATUS_DONE: ("done", done_label, None),
        TOOL_STATUS_ERROR: ("error", error_label, result.get("error")),
        TOOL_STATUS_INVALID: (
            "error",
            "La propuesta no pasó la revisión",
            result.get("error"),
        ),
        TOOL_STATUS_REJECTED: ("rejected", "Descartaste la propuesta", None),
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
    if row.tool_name == "cancel_publication":
        publication = await _existing_publication(session, ctx, arguments.get("publication_id"))
        return {
            "id": row.tool_call_id,
            "tool": "cancel_publication",
            "title": "Borrar publicación",
            "confirm_label": "Borrar",
            "publication": publication,
        }
    scheduled_for = _parse_datetime(arguments.get("scheduled_for"))
    content = arguments.get("content")
    return {
        "id": row.tool_call_id,
        "tool": "create_publication",
        "title": "Programar publicación",
        "confirm_label": "Programar" if scheduled_for is not None else "Publicar ahora",
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


__all__ = ["present_thread", "present_thread_summary"]
