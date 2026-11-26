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

A call the business makes (``direction`` ``outbound``) starts ``ringing``
with ``answered_by_id`` already set to the agent calling; the customer's
WebRTC answer arrives in ``sdp_answer`` and the call is ``in_progress`` once
they pick up. Making one needs the customer's permission (Meta keeps it).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
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
DIRECTION_OUTBOUND = "outbound"
PROVIDER_WHATSAPP = "whatsapp"

# Languages Meta can read the recording notice in (``announcement_language``).
ANNOUNCEMENT_LANGUAGES = ("es", "es_ES", "en", "pt", "fr", "de", "it", "nl", "hi", "kn", "te", "vi")
PURPOSE_MAX = 250
# What the customer reads after a call nobody answered.
MISSED_TEXT_MAX = 1024

# Who answers the inbox's calls (F7 paso 3): the people of the inbox, or
# AloStudio's voice AI always, outside the inbox's hours, or when nobody
# picked up in ``AI_NO_ANSWER_SECONDS``.
AI_MODE_OFF = "off"
AI_MODE_ALWAYS = "always"
AI_MODE_AFTER_HOURS = "after_hours"
AI_MODE_NO_ANSWER = "no_answer"
AI_MODES = (AI_MODE_OFF, AI_MODE_ALWAYS, AI_MODE_AFTER_HOURS, AI_MODE_NO_ANSWER)
AI_NO_ANSWER_SECONDS = 20
AI_GREETING_MAX = 500
AI_INSTRUCTIONS_MAX = 4000
# Gemini Live's prebuilt voices offered in the panel.
AI_VOICES = ("Charon", "Puck", "Kore", "Aoede", "Fenrir", "Leda", "Orus", "Zephyr")


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
    # For a call we make: the customer's answer, which the agent's browser
    # applies to the offer it sent.
    sdp_answer: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
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

    # Recording and transcription, when the inbox asked Meta for them. Meta
    # keeps the files 7 days after announcing them (``*_available_at``); the
    # media id stays until our copy is made, so a failed copy is retried.
    recording_requested: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    transcription_requested: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    recording_media_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    recording_available_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    recording_attachment_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    transcript_media_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    transcript_available_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    # ``[{"speaker": "business"|"customer", "text": "…", "start": s}]``
    transcript: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True), nullable=True)
    )
    transcript_language: str | None = Field(
        default=None, sa_column=Column(String(16), nullable=True)
    )
    # What the call was about, written by the AI from the transcript (F17),
    # while the installation's operator has it on. Tries are counted so a
    # call the model keeps failing on is left alone.
    summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    summary_attempts: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    # Answered by the voice AI instead of a person (``answered_by_id`` empty).
    ai_answered: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )


class CallInboxSettings(TimestampMixin, table=True):
    """What an inbox does with its calls beyond answering them: record them,
    transcribe them, and what the notice tells both sides. Only applies
    while the installation allows recording (``call_recording_allowed``)."""

    __tablename__ = "call_inbox_settings"

    inbox_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("inboxes.id", ondelete="CASCADE"), primary_key=True
        )
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    record: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    transcribe: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # Said to both sides before recording ("…será grabado con el siguiente fin: <purpose>").
    purpose: str | None = Field(default=None, sa_column=Column(String(PURPOSE_MAX), nullable=True))
    announcement_language: str = Field(
        default="es", sa_column=Column(String(8), nullable=False, server_default="es")
    )
    # A call nobody answered: tell the customer we call back (on unless
    # turned off), with this text or ours.
    missed_call_reply: bool = Field(
        default=True, sa_column=Column(Boolean, nullable=False, server_default="true")
    )
    missed_call_text: str | None = Field(
        default=None, sa_column=Column(String(MISSED_TEXT_MAX), nullable=True)
    )
    # The voice AI (F7 paso 3): when it answers, what it says first (it
    # always adds that it is an AI and that what it says is not binding),
    # what it must know about the business and which voice it speaks with.
    ai_mode: str = Field(
        default=AI_MODE_OFF,
        sa_column=Column(String(16), nullable=False, server_default=AI_MODE_OFF),
    )
    ai_greeting: str | None = Field(
        default=None, sa_column=Column(String(AI_GREETING_MAX), nullable=True)
    )
    ai_instructions: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ai_voice: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
