"""Contact lifecycle (F17): the account's stages, moving a contact between
them, the default stage on a contact's first message, and the counts."""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.lifecycle.models import (
    DESCRIPTION_MAX,
    EMOJI_MAX,
    KEY_MAX,
    KIND_LOST,
    KIND_STAGE,
    NAME_MAX,
    STAGES_MAX,
    ContactLifecycle,
    LifecycleChange,
    LifecycleSettings,
)
from app.domains.users.models import User

log = logging.getLogger(__name__)

# respond.io's: four steps to a sale and one way out.
DEFAULTS = (
    ("new_lead", "🆕", KIND_STAGE, True),
    ("hot_lead", "🔥", KIND_STAGE, False),
    ("payment", "💳", KIND_STAGE, False),
    ("customer", "🤩", KIND_STAGE, False),
    ("cold_lead", "🧊", KIND_LOST, False),
)
_KEY = re.compile(r"[a-z0-9_]{1,40}")


def _now() -> datetime:
    return datetime.now(UTC)


def default_stages() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "name": t(DEFAULT_LOCALE, f"lifecycle.default.{key}.name"),
            "description": t(DEFAULT_LOCALE, f"lifecycle.default.{key}.description"),
            "emoji": emoji,
            "kind": kind,
            "default": default,
        }
        for key, emoji, kind, default in DEFAULTS
    ]


def _slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", plain).strip("_")[:KEY_MAX] or "stage"


def stages_of(row: LifecycleSettings | None) -> list[dict[str, Any]]:
    return list(row.stages) if row is not None and row.stages else default_stages()


def _stage(stages: list[dict[str, Any]], key: str | None) -> dict[str, Any] | None:
    return next((s for s in stages if s["key"] == key), None) if key else None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
async def present_settings(session: AsyncSession, account_id: int) -> dict[str, Any]:
    row = await session.get(LifecycleSettings, account_id)
    return {"enabled": bool(row and row.enabled), "stages": stages_of(row)}


def clean_stages(raw: Any) -> list[dict[str, Any]]:
    """The stages as typed, trimmed, each with a stable key. Raises
    ValueError (a short code) when they do not hold up."""
    if not isinstance(raw, list) or not raw or len(raw) > STAGES_MAX:
        raise ValueError("stages")
    out: list[dict[str, Any]] = []
    names: set[str] = set()
    keys: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("stages")
        name = " ".join(str(item.get("name") or "").split())
        if not name or len(name) > NAME_MAX:
            raise ValueError("name")
        if name.casefold() in names:
            raise ValueError("duplicate_name")
        names.add(name.casefold())
        kind = item.get("kind") or KIND_STAGE
        if kind not in (KIND_STAGE, KIND_LOST):
            raise ValueError("kind")
        description = " ".join(str(item.get("description") or "").split())
        if len(description) > DESCRIPTION_MAX:
            raise ValueError("description")
        given = item.get("key")
        key = given if isinstance(given, str) and _KEY.fullmatch(given) else _slug(name)
        base, n = key, 2
        while key in keys:
            key = f"{base[: KEY_MAX - 4]}_{n}"
            n += 1
        keys.add(key)
        is_default = bool(item.get("default"))
        if is_default and kind == KIND_LOST:
            raise ValueError("default")
        out.append(
            {
                "key": key,
                "name": name,
                "emoji": str(item.get("emoji") or "").strip()[:EMOJI_MAX],
                "description": description,
                "kind": kind,
                "default": is_default,
            }
        )
    if sum(1 for s in out if s["default"]) > 1:
        raise ValueError("default")
    if not any(s["kind"] == KIND_STAGE for s in out):
        raise ValueError("no_stage")
    return out


async def save_settings(
    session: AsyncSession, *, account_id: int, enabled: bool, stages: Any | None
) -> dict[str, Any]:
    row = await session.get(LifecycleSettings, account_id)
    if row is None:
        row = LifecycleSettings(account_id=account_id)
    row.enabled = enabled
    if stages is not None:
        cleaned = clean_stages(stages)
        row.stages = cleaned
        # Contacts in a stage that is gone stand in none.
        await session.exec(
            delete(ContactLifecycle).where(
                ContactLifecycle.account_id == account_id,  # type: ignore[arg-type]
                ContactLifecycle.stage_key.not_in([s["key"] for s in cleaned]),  # type: ignore[attr-defined]
            )
        )
    session.add(row)
    await session.flush()
    return await present_settings(session, account_id)


# ---------------------------------------------------------------------------
# A contact's stage
# ---------------------------------------------------------------------------
async def contact_stage(session: AsyncSession, *, account_id: int, contact_id: int) -> dict[str, Any]:
    row = await session.get(ContactLifecycle, contact_id)
    if row is None or row.account_id != account_id:
        return {"stage": None, "changed_at": None, "changed_by": None}
    stages = stages_of(await session.get(LifecycleSettings, account_id))
    user = await session.get(User, row.changed_by_id) if row.changed_by_id else None
    return {
        "stage": _stage(stages, row.stage_key),
        "changed_at": row.changed_at,
        "changed_by": (
            {"id": user.id, "name": user.available_name or user.name} if user is not None else None
        ),
    }


async def _move(
    session: AsyncSession,
    *,
    account_id: int,
    contact_id: int,
    stage: dict[str, Any] | None,
    user_id: int | None,
) -> bool:
    """Put the contact in ``stage`` (``None``: in none). False when they
    already stood there."""
    row = await session.get(ContactLifecycle, contact_id)
    before = row.stage_key if row is not None else None
    after = stage["key"] if stage else None
    if before == after:
        return False
    if after is None:
        await session.delete(row)
    else:
        if row is None:
            row = ContactLifecycle(
                contact_id=contact_id,
                account_id=account_id,
                stage_key=after,
                changed_at=_now(),
                changed_by_id=user_id,
            )
        row.stage_key = after
        row.changed_at = _now()
        row.changed_by_id = user_id
        session.add(row)
    session.add(
        LifecycleChange(
            account_id=account_id,
            contact_id=contact_id,
            from_key=before,
            to_key=after,
            user_id=user_id,
        )
    )
    await session.flush()
    return True


async def _tell_meta(session: AsyncSession, *, account_id: int, contact_id: int, stage: dict[str, Any]) -> None:
    """A stage the account maps to a Conversions API event queues it.
    Never in the way of the move."""
    from app.domains.conversions.service import on_lifecycle

    try:
        async with session.begin_nested():
            await on_lifecycle(
                session,
                account_id=account_id,
                contact_id=contact_id,
                stage_key=stage["key"],
                stage_name=stage["name"],
            )
    except Exception:
        log.exception("lifecycle.conversions_failed contact_id=%s", contact_id)


async def set_stage(
    session: AsyncSession,
    *,
    account_id: int,
    contact: Contact,
    stage_key: str | None,
    user: User | None,
    conversation: Conversation | None = None,
) -> dict[str, Any]:
    """Move a contact (``None``: out of every stage). The conversation it was
    done from gets a line saying so. Raises ValueError (``disabled`` /
    ``stage``) before changing anything."""
    from app.domains.conversations.activities import create_activity_message

    settings = await session.get(LifecycleSettings, account_id)
    if settings is None or not settings.enabled:
        raise ValueError("disabled")
    stage = _stage(stages_of(settings), stage_key)
    if stage_key and stage is None:
        raise ValueError("stage")
    assert contact.id is not None
    moved = await _move(
        session,
        account_id=account_id,
        contact_id=contact.id,
        stage=stage,
        user_id=user.id if user is not None else None,
    )
    if moved and conversation is not None and conversation.contact_id == contact.id:
        who = (user.available_name or user.name) if user is not None else t(DEFAULT_LOCALE, "lifecycle.someone")
        content = (
            t(DEFAULT_LOCALE, "lifecycle.activity", name=who, stage=f"{stage['emoji']} {stage['name']}".strip())
            if stage
            else t(DEFAULT_LOCALE, "lifecycle.activity_cleared", name=who)
        )
        await create_activity_message(session, conversation=conversation, content=content)
    if moved and stage is not None:
        await _tell_meta(session, account_id=account_id, contact_id=contact.id, stage=stage)
    return await contact_stage(session, account_id=account_id, contact_id=contact.id)


async def on_first_message(session: AsyncSession, *, account_id: int, contact_id: int) -> None:
    """A contact who writes and stands in no stage goes to the default one."""
    settings = await session.get(LifecycleSettings, account_id)
    if settings is None or not settings.enabled:
        return
    if await session.get(ContactLifecycle, contact_id) is not None:
        return
    default = next((s for s in stages_of(settings) if s.get("default")), None)
    if default is None:
        return
    if await _move(session, account_id=account_id, contact_id=contact_id, stage=default, user_id=None):
        await _tell_meta(session, account_id=account_id, contact_id=contact_id, stage=default)


# ---------------------------------------------------------------------------
# How many stand where
# ---------------------------------------------------------------------------
async def report(session: AsyncSession, *, account_id: int, days: int = 30) -> dict[str, Any]:
    """Per stage: contacts in it now, and how many entered it in ``days``."""
    settings = await session.get(LifecycleSettings, account_id)
    now_rows = (
        await session.exec(
            select(ContactLifecycle.stage_key, func.count())
            .where(ContactLifecycle.account_id == account_id)
            .group_by(ContactLifecycle.stage_key)
        )
    ).all()
    since = _now() - timedelta(days=days)
    entered_rows = (
        await session.exec(
            select(LifecycleChange.to_key, func.count())
            .where(
                LifecycleChange.account_id == account_id,
                LifecycleChange.created_at >= since,
                LifecycleChange.to_key.is_not(None),  # type: ignore[union-attr]
            )
            .group_by(LifecycleChange.to_key)
        )
    ).all()
    now_counts = {key: int(n) for key, n in now_rows}
    entered = {key: int(n) for key, n in entered_rows}
    return {
        "days": days,
        "enabled": bool(settings and settings.enabled),
        "stages": [
            {
                "key": s["key"],
                "name": s["name"],
                "emoji": s["emoji"],
                "kind": s["kind"],
                "count": now_counts.get(s["key"], 0),
                "entered": entered.get(s["key"], 0),
            }
            for s in stages_of(settings)
        ],
    }


__all__ = [
    "clean_stages",
    "contact_stage",
    "default_stages",
    "on_first_message",
    "present_settings",
    "report",
    "save_settings",
    "set_stage",
    "stages_of",
]
