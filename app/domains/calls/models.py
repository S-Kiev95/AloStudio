"""Voice calls (F7): one row per call, whatever channel carried it.

Today only WhatsApp (Business Calling API) carries calls: a customer calls
the business number and an agent answers from the browser. The conversation
gets a ``voice_call`` message per call (Chatwoot's shape: ``content_type``
``voice_call`` and the state in ``content_attributes.data``); this table is
the source of truth behind it: who took the call, the offer the browser
needs to answer it, and how it ended.

Statuses:

* ``ringing`` — Meta announced the call; every agent of the inbox sees it.
* ``connecting`` — one agent took it (``answered_by_id``) and the audio is
  being set up. Nobody else can take it any more.
* ``in_progress`` — Meta confirmed the answer; the audio flows.
* ``completed`` / ``missed`` / ``failed`` — over. ``missed`` is a call that
  nobody answered.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlmodel import Field

from app.core.base_model import TimestampMixin

CALL_RINGING = "ringing"
CALL_CONNECTING = "connecting"
CALL_IN_PROGRESS = "in_progress"
CALL_COMPLETED = "completed"
CALL_MISSED = "missed"
CALL_FAILED = "failed"

ACTIVE_STATUSES = (CALL_RINGING, CALL_CONNECTING, CALL_IN_PROGRESS)
FINAL_STATUSES = (CALL_COMPLETED, CALL_MISSED, CALL_FAILED)

DIRECTION_INBOUND = "inbound"
PROVIDER_WHATSAPP = "whatsapp"


class Call(TimestampMixin, table=True):
    """A voice call in a conversation."""

    __tablename__ = "calls"
    __table_args__ = (
        Index("index_calls_on_account_id_and_status", "account_id", "status"),
        Index("index_calls_on_provider_call_id", "provider_call_id", unique=True),
        Index("index_calls_on_conversation_id", "conversation_id"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    inbox_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("inboxes.id", ondelete="CASCADE"), nullable=False)
    )
    conversation_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
        )
    )
    contact_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
        ),
    )
    # The ``voice_call`` message that shows the call in the conversation.
    message_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
        ),
    )
    provider: str = Field(
        default=PROVIDER_WHATSAPP, sa_column=Column(String(16), nullable=False)
    )
    # Meta's call id (``wacid.…``): the key every later event refers to.
    provider_call_id: str = Field(sa_column=Column(String, nullable=False))
    direction: str = Field(
        default=DIRECTION_INBOUND, sa_column=Column(String(8), nullable=False)
    )
    status: str = Field(default=CALL_RINGING, sa_column=Column(String(16), nullable=False))
    from_number: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    to_number: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    # The caller's WebRTC offer, which the agent's browser answers. Only
    # useful while the call rings; cleared when it ends.
    sdp_offer: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    answered_by_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    answered_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    ended_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    duration_seconds: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    # Why it failed, as Meta put it (``code: message``), for whoever looks.
    end_reason: str | None = Field(default=None, sa_column=Column(String, nullable=True))
