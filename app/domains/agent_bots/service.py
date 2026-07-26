"""AgentBot CRUD service + AgentBotInbox attach/detach.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/agent_bots_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/inboxes_controller.rb
    (set_agent_bot member action)
  reference/chatwoot/app/models/concerns/webhook_secretable.rb (secret generator)
"""

from __future__ import annotations

import secrets
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.agent_bots.models import (
    AGENT_BOT_INBOX_STATUS_ACTIVE,
    AGENT_BOT_TYPE_WEBHOOK,
    AgentBot,
    AgentBotInbox,
)
from app.domains.inboxes.models import Inbox


def _new_secret() -> str:
    """Mirror Chatwoot's ``WebhookSecretable`` — SecureRandom.hex(12) →
    24-char lowercase hex string. ``secrets.token_hex(12)`` yields the
    same shape."""
    return secrets.token_hex(12)


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------
async def list_bots_accessible_to(
    session: AsyncSession, *, account_id: int
) -> list[AgentBot]:
    """Mirror ``AgentBot.accessible_to`` — every bot whose
    ``account_id`` is either NULL (system bot) or the current account.

    System-bot rows are shared across all accounts; account-owned bots
    are private. Phase 8 ships no system bots, but the visibility
    contract preserves the door for them.
    """
    stmt = (
        select(AgentBot)
        .where(
            (AgentBot.account_id == account_id)
            | (AgentBot.account_id.is_(None))  # type: ignore[union-attr]
        )
        .order_by(AgentBot.id.asc())
    )
    return list((await session.exec(stmt)).all())


async def fetch_account_bot(
    session: AsyncSession, *, account_id: int, bot_id: int
) -> AgentBot | None:
    """Account-scoped fetch — used by mutating actions which Chatwoot
    restricts to the bot's owner account (no system-bot edits)."""
    return (
        await session.exec(
            select(AgentBot).where(
                AgentBot.id == bot_id, AgentBot.account_id == account_id
            )
        )
    ).first()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def create_bot(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> AgentBot:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Name can't be blank"}
        )
    bot = AgentBot(
        account_id=account_id,
        name=name,
        description=payload.get("description"),
        outgoing_url=payload.get("outgoing_url"),
        bot_type=AGENT_BOT_TYPE_WEBHOOK,
        bot_config=payload.get("bot_config") or {},
        secret=_new_secret(),
    )
    session.add(bot)
    await session.flush()
    await session.refresh(bot)
    return bot


async def update_bot(
    session: AsyncSession,
    *,
    bot: AgentBot,
    payload: dict[str, Any],
) -> AgentBot:
    if "name" in payload:
        new_name = (payload.get("name") or "").strip()
        if not new_name:
            raise ChatwootHTTPException(
                status_code=422, detail={"message": "Name can't be blank"}
            )
        bot.name = new_name
    if "description" in payload:
        bot.description = payload.get("description")
    if "outgoing_url" in payload:
        bot.outgoing_url = payload.get("outgoing_url")
    if "bot_config" in payload:
        bot.bot_config = payload.get("bot_config") or {}
    session.add(bot)
    await session.flush()
    await session.refresh(bot)
    return bot


async def destroy_bot(session: AsyncSession, *, bot: AgentBot) -> None:
    await session.delete(bot)
    await session.flush()


async def reset_bot_secret(
    session: AsyncSession, *, bot: AgentBot
) -> AgentBot:
    """Mirror ``AgentBot#reset_secret!`` — rotates the HMAC signing key."""
    bot.secret = _new_secret()
    session.add(bot)
    await session.flush()
    await session.refresh(bot)
    return bot


# ---------------------------------------------------------------------------
# Attach / detach (the inbox-side endpoint)
# ---------------------------------------------------------------------------
async def attach_bot_to_inbox(
    session: AsyncSession,
    *,
    account_id: int,
    inbox: Inbox,
    agent_bot_id: int,
) -> AgentBotInbox:
    """Mirror ``InboxesController#set_agent_bot``.

    Removes any existing attach first (Rails ``destroy_agent_bot_inbox``
    runs before each set) so only one bot lives on an inbox at a time.
    """
    # Drop any prior attach.
    existing = list(
        (
            await session.exec(
                select(AgentBotInbox).where(
                    AgentBotInbox.inbox_id == inbox.id
                )
            )
        ).all()
    )
    for row in existing:
        await session.delete(row)
    if existing:
        await session.flush()

    # Verify the bot is accessible to this account (system OR same account).
    bot = (
        await session.exec(
            select(AgentBot).where(
                AgentBot.id == agent_bot_id,
                (AgentBot.account_id == account_id)
                | (AgentBot.account_id.is_(None)),  # type: ignore[union-attr]
            )
        )
    ).first()
    if bot is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )

    join = AgentBotInbox(
        account_id=account_id,
        inbox_id=inbox.id,
        agent_bot_id=agent_bot_id,
        status=AGENT_BOT_INBOX_STATUS_ACTIVE,
    )
    session.add(join)
    await session.flush()
    await session.refresh(join)
    return join


async def detach_bot_from_inbox(
    session: AsyncSession, *, inbox: Inbox
) -> None:
    existing = list(
        (
            await session.exec(
                select(AgentBotInbox).where(
                    AgentBotInbox.inbox_id == inbox.id
                )
            )
        ).all()
    )
    for row in existing:
        await session.delete(row)
    if existing:
        await session.flush()


async def attached_bot_for_inbox(
    session: AsyncSession, *, inbox_id: int
) -> AgentBot | None:
    """Return the active bot attached to ``inbox_id`` (or None).

    Used by the 8.2 listener to decide whether to relay a message."""
    join = (
        await session.exec(
            select(AgentBotInbox).where(
                AgentBotInbox.inbox_id == inbox_id,
                AgentBotInbox.status == AGENT_BOT_INBOX_STATUS_ACTIVE,
            )
        )
    ).first()
    if join is None or join.agent_bot_id is None:
        return None
    return await session.get(AgentBot, join.agent_bot_id)


__all__ = [
    "attach_bot_to_inbox",
    "attached_bot_for_inbox",
    "create_bot",
    "destroy_bot",
    "detach_bot_from_inbox",
    "fetch_account_bot",
    "list_bots_accessible_to",
    "reset_bot_secret",
    "update_bot",
]
