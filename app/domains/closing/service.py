"""Closing notes (F17): the account's categories, closing a conversation with
one, and how many closed for each reason."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.closing.models import (
    CATEGORIES_MAX,
    CATEGORY_MAX,
    NOTE_MAX,
    ClosingSettings,
    ConversationClosing,
)
from app.domains.conversations.models import Conversation

DEFAULT_KEYS = ("answered", "enrolled", "not_interested", "no_reply", "spam")


def _now() -> datetime:
    return datetime.now(UTC)


def default_categories() -> list[str]:
    return [t(DEFAULT_LOCALE, f"closing.default.{key}") for key in DEFAULT_KEYS]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
async def get_row(session: AsyncSession, account_id: int) -> ClosingSettings | None:
    return await session.get(ClosingSettings, account_id)


def _present(row: ClosingSettings | None) -> dict[str, Any]:
    return {
        "enabled": bool(row and row.enabled),
        "required": bool(row and row.required),
        "categories": list(row.categories) if row and row.categories else default_categories(),
    }


async def present_settings(session: AsyncSession, account_id: int) -> dict[str, Any]:
    return _present(await get_row(session, account_id))


def clean_categories(raw: Any) -> list[str]:
    """The categories as typed, trimmed. Raises ValueError (a short code) when
    they do not hold up: none, too many, too long, or the same one twice."""
    if not isinstance(raw, list):
        raise ValueError("categories")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("categories")
        title = " ".join(item.split())
        if not title:
            continue
        if len(title) > CATEGORY_MAX:
            raise ValueError("category_length")
        if title.casefold() in seen:
            raise ValueError("duplicate_category")
        seen.add(title.casefold())
        out.append(title)
    if not out or len(out) > CATEGORIES_MAX:
        raise ValueError("categories")
    return out


async def save_settings(
    session: AsyncSession,
    *,
    account_id: int,
    enabled: bool,
    required: bool,
    categories: Any | None,
) -> dict[str, Any]:
    row = await get_row(session, account_id)
    if row is None:
        row = ClosingSettings(account_id=account_id)
    row.enabled = enabled
    row.required = required
    if categories is not None:
        row.categories = clean_categories(categories)
    session.add(row)
    await session.flush()
    return _present(row)


# ---------------------------------------------------------------------------
# Closing a conversation
# ---------------------------------------------------------------------------
async def close(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_id: int,
    category: str | None,
    note: str | None,
) -> ConversationClosing | None:
    """Resolve the conversation, keeping why. The reason and the note stay
    as a private note in the conversation too. ``None`` when it closed with
    neither (allowed unless the account requires a category). Raises
    ValueError (a short code) before changing anything."""
    from app.domains.conversations.service import (
        MessageBuilderParams,
        create_message,
        toggle_status,
    )

    settings = await present_settings(session, conversation.account_id)
    if not settings["enabled"]:
        raise ValueError("disabled")
    chosen = " ".join((category or "").split()) or None
    said = (note or "").strip() or None
    if chosen is None and settings["required"]:
        raise ValueError("required")
    if chosen is not None and chosen not in settings["categories"]:
        raise ValueError("category")
    if said is not None and len(said) > NOTE_MAX:
        raise ValueError("note")

    await toggle_status(session, conversation=conversation, status="resolved")
    if chosen is None and said is None:
        return None

    title = t(DEFAULT_LOCALE, "closing.note_title")
    text = f"{title}: {chosen}" if chosen else title
    if said:
        text = f"{text}\n{said}"
    message = await create_message(
        session,
        conversation=conversation,
        params=MessageBuilderParams(
            content=text,
            message_type="outgoing",
            private=True,
            content_attributes={"closing_note": {"category": chosen}},
        ),
        user_id=user_id,
    )
    row = ConversationClosing(
        account_id=conversation.account_id,
        conversation_id=conversation.id,
        category=chosen,
        note=said,
        user_id=user_id,
        message_id=message.id,
    )
    session.add(row)
    await session.flush()
    return row


# ---------------------------------------------------------------------------
# How conversations close
# ---------------------------------------------------------------------------
async def report(session: AsyncSession, *, account_id: int, days: int = 30) -> dict[str, Any]:
    """Closings in the last ``days``, by category (most first; ``None`` for
    the ones closed with a note only)."""
    since = _now() - timedelta(days=days)
    rows = (
        await session.exec(
            select(ConversationClosing.category, func.count())
            .where(
                ConversationClosing.account_id == account_id,
                ConversationClosing.created_at >= since,
            )
            .group_by(ConversationClosing.category)
        )
    ).all()
    counts: list[tuple[str | None, int]] = [(category, int(n)) for category, n in rows]
    counts.sort(key=lambda c: (-c[1], c[0] is None, c[0] or ""))
    return {
        "days": days,
        "total": sum(n for _, n in counts),
        "categories": [{"category": category, "count": n} for category, n in counts],
    }


__all__ = [
    "clean_categories",
    "close",
    "default_categories",
    "present_settings",
    "report",
    "save_settings",
]
