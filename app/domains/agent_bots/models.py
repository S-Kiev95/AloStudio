"""AgentBot + AgentBotInbox — programmable conversation participants.

Ported from:
  reference/chatwoot/app/models/agent_bot.rb
  reference/chatwoot/app/models/agent_bot_inbox.rb
  reference/chatwoot/db/schema.rb (agent_bots / agent_bot_inboxes tables)

A bot is an HTTP receiver the account configures with an
``outgoing_url``: every message on an inbox the bot is attached to
gets POSTed there. The bot replies via the regular Chatwoot HTTP API
authenticated with its ``access_token``. ``secret`` signs outbound
POSTs.

A ``system bot`` is a bot with ``account_id IS NULL`` — shared across
the install (Phase 8 doesn't ship any built-in system bots; the flag
is preserved on the wire for parity).

The join table ``agent_bot_inboxes`` is the (inbox_id, agent_bot_id)
attach record. Status enum is reserved for future "paused" semantics
that Chatwoot ships but never reads in v4.13.0; we mirror the column
verbatim.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# enum bot_type: {webhook: 0}
AGENT_BOT_TYPE_WEBHOOK = 0

# enum status on AgentBotInbox: {active: 0, paused: 1}
AGENT_BOT_INBOX_STATUS_ACTIVE = 0
AGENT_BOT_INBOX_STATUS_PAUSED = 1


class AgentBot(TimestampMixin, table=True):
    """An HTTP-driven conversation participant."""

    __tablename__ = "agent_bots"
    __table_args__ = (
        Index("index_agent_bots_on_account_id", "account_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    description: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    outgoing_url: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    bot_type: int = Field(
        default=AGENT_BOT_TYPE_WEBHOOK,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    bot_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    secret: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    @property
    def system_bot(self) -> bool:
        return self.account_id is None


class AgentBotInbox(TimestampMixin, table=True):
    """One row per (inbox, agent_bot) attach.

    Chatwoot stores ``account_id`` redundantly on the join too — we
    mirror because the dashboard's "remove bot" path filters by
    account_id without joining out.
    """

    __tablename__ = "agent_bot_inboxes"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    inbox_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    agent_bot_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("agent_bots.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    status: int = Field(
        default=AGENT_BOT_INBOX_STATUS_ACTIVE,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )


__all__ = [
    "AGENT_BOT_INBOX_STATUS_ACTIVE",
    "AGENT_BOT_INBOX_STATUS_PAUSED",
    "AGENT_BOT_TYPE_WEBHOOK",
    "AgentBot",
    "AgentBotInbox",
]
