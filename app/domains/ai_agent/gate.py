"""When AloStudio's AI answers a conversation (PLAN.agente-ia.md, 2b).

A bot of type AI attached to an inbox (Ajustes → Bots, then the inbox)
answers its customers. Its ``bot_config``:

  * ``instructions`` — what the business tells it (tone, what to offer,
    when to hand off);
  * ``mode`` — ``shadow`` proposes each answer to the team, ``live`` sends
    it;
  * ``respond_when`` — ``always``, ``out_of_hours`` (outside the inbox's
    working hours, when it has them on) or ``nobody_available`` (no member
    of the inbox is "online"; availability is what each person sets).

Live, a conversation the AI holds is ``pending`` with the bot as
``assignee_agent_bot_id`` (Chatwoot's bot convention): auto-assignment
leaves it alone and it opens when the AI hands off or a person answers.
Shadow takes nothing: it only proposes.

Only models are imported here, so the conversations service can ask.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import llm
from app.domains.agent_bots.models import AGENT_BOT_TYPE_AI, AgentBot
from app.domains.agent_bots.service import attached_bot_for_inbox
from app.domains.ai_agent.models import MODE_LIVE, MODE_SHADOW, MODES
from app.domains.conversations.models import Conversation
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    Inbox,
    InboxMember,
    WhatsappChannel,
)
from app.domains.users.models import USER_AVAILABILITY_ONLINE, AccountUser

RESPOND_ALWAYS = "always"
RESPOND_OUT_OF_HOURS = "out_of_hours"
RESPOND_NOBODY_AVAILABLE = "nobody_available"
RESPOND_WHEN = (RESPOND_ALWAYS, RESPOND_OUT_OF_HOURS, RESPOND_NOBODY_AVAILABLE)

INSTRUCTIONS_MAX = 4000
# Appointment lengths the AI can offer (minutes).
SLOT_MINUTES = (15, 30, 45, 60, 90, 120)
SLOT_MINUTES_DEFAULT = 60


@dataclass(frozen=True, slots=True)
class AiConfig:
    instructions: str
    mode: str
    respond_when: str
    # What it may do besides answering (off until an administrator allows
    # it): book in the Agenda inside the inbox's hours, and write the
    # contact's data, stage, labels and opportunities.
    can_book: bool = False
    slot_minutes: int = SLOT_MINUTES_DEFAULT
    can_update_crm: bool = False


def parse_config(raw: dict[str, Any] | None) -> AiConfig:
    """The stored config, with defaults for what is missing or unknown."""
    raw = raw if isinstance(raw, dict) else {}
    mode = raw.get("mode")
    when = raw.get("respond_when")
    slot = raw.get("slot_minutes")
    return AiConfig(
        instructions=str(raw.get("instructions") or "")[:INSTRUCTIONS_MAX],
        mode=mode if mode in MODES else MODE_SHADOW,
        respond_when=when if when in RESPOND_WHEN else RESPOND_ALWAYS,
        can_book=raw.get("can_book") is True,
        slot_minutes=slot if slot in SLOT_MINUTES else SLOT_MINUTES_DEFAULT,
        can_update_crm=raw.get("can_update_crm") is True,
    )


def validate_config(raw: Any) -> dict[str, Any]:
    """The config to store, or ``ValueError`` naming the bad field."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("bot_config")
    instructions = raw.get("instructions") or ""
    if not isinstance(instructions, str) or len(instructions) > INSTRUCTIONS_MAX:
        raise ValueError("instructions")
    mode = raw.get("mode") or MODE_SHADOW
    if mode not in MODES:
        raise ValueError("mode")
    when = raw.get("respond_when") or RESPOND_ALWAYS
    if when not in RESPOND_WHEN:
        raise ValueError("respond_when")
    for flag in ("can_book", "can_update_crm"):
        if not isinstance(raw.get(flag, False), bool):
            raise ValueError(flag)
    slot = raw.get("slot_minutes", SLOT_MINUTES_DEFAULT)
    if slot not in SLOT_MINUTES or isinstance(slot, bool):
        raise ValueError("slot_minutes")
    return {
        "instructions": instructions.strip(),
        "mode": mode,
        "respond_when": when,
        "can_book": raw.get("can_book", False),
        "slot_minutes": slot,
        "can_update_crm": raw.get("can_update_crm", False),
    }


async def inbox_ai_bot(session: AsyncSession, inbox_id: int | None) -> AgentBot | None:
    """The AI bot attached to the inbox, if the attached bot is one."""
    if inbox_id is None:
        return None
    bot = await attached_bot_for_inbox(session, inbox_id=inbox_id)
    return bot if bot is not None and bot.bot_type == AGENT_BOT_TYPE_AI else None


def is_live(bot: AgentBot | None) -> bool:
    return bot is not None and parse_config(bot.bot_config).mode == MODE_LIVE


async def _somebody_available(session: AsyncSession, inbox: Inbox) -> bool:
    found = (
        await session.exec(
            select(InboxMember.id)
            .join(AccountUser, AccountUser.user_id == InboxMember.user_id)  # type: ignore[arg-type]
            .where(
                InboxMember.inbox_id == inbox.id,
                AccountUser.account_id == inbox.account_id,
                AccountUser.availability == USER_AVAILABILITY_ONLINE,
            )
        )
    ).first()
    return found is not None


async def wants_to_answer(
    session: AsyncSession, bot: AgentBot, inbox: Inbox, *, now: datetime | None = None
) -> bool:
    """Whether the bot's "when it answers" holds right now in this inbox."""
    when = parse_config(bot.bot_config).respond_when
    if when == RESPOND_OUT_OF_HOURS:
        if not inbox.working_hours_enabled:
            return False
        from app.domains.working_hours.service import list_for_inbox, open_at

        rows = await list_for_inbox(session, inbox_id=inbox.id)  # type: ignore[arg-type]
        return not open_at(rows=rows, timezone_name=inbox.timezone, moment=now or datetime.now(UTC))
    if when == RESPOND_NOBODY_AVAILABLE:
        return not await _somebody_available(session, inbox)
    return True


async def meta_answers_inbox(session: AsyncSession, inbox: Inbox) -> bool:
    """The inbox's WhatsApp number has Meta's agent answering new chats:
    AloStudio's AI only gets the ones Meta hands to it (``bot_handoff``)."""
    if inbox.channel_type != CHANNEL_TYPE_WHATSAPP or inbox.channel_id is None:
        return False
    channel = await session.get(WhatsappChannel, inbox.channel_id)
    if channel is None:
        return False
    # Late import: the WhatsApp domain imports the conversations service.
    from app.domains.whatsapp.business_agent import business_agent_enabled

    return business_agent_enabled(channel)


async def taker_for(session: AsyncSession, inbox: Inbox) -> AgentBot | None:
    """The live AI bot that takes a new (or reopened) conversation of this
    inbox right now, or None (it goes to the team as before)."""
    # Without the OpenAI key it could only fail and hand off.
    if not llm.embedding_search_enabled():
        return None
    bot = await inbox_ai_bot(session, inbox.id)
    if not is_live(bot) or await meta_answers_inbox(session, inbox):
        return None
    assert bot is not None
    return bot if await wants_to_answer(session, bot, inbox) else None


def held_by_ai(conversation: Conversation, bot: AgentBot | None) -> bool:
    """The live AI holds the conversation (it answers its customer)."""
    return (
        bot is not None
        and bot.id is not None
        and conversation.assignee_agent_bot_id == bot.id
        and conversation.assignee_id is None
    )


__all__ = [
    "INSTRUCTIONS_MAX",
    "RESPOND_ALWAYS",
    "RESPOND_NOBODY_AVAILABLE",
    "RESPOND_OUT_OF_HOURS",
    "RESPOND_WHEN",
    "SLOT_MINUTES",
    "AiConfig",
    "held_by_ai",
    "inbox_ai_bot",
    "is_live",
    "meta_answers_inbox",
    "parse_config",
    "taker_for",
    "validate_config",
    "wants_to_answer",
]
