"""Google Calendar links (F17): who connected their calendar, and which
Google event stands for which appointment or task."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlmodel import Field

from app.core.base_model import TimestampMixin

SOURCE_APPOINTMENT = "appointment"
SOURCE_ACTIVITY = "activity"


class GoogleCalendarLink(TimestampMixin, table=True):
    """One per user: the refresh token Google gave when they connected,
    encrypted with a key derived from the app's secret."""

    __tablename__ = "google_calendar_links"

    user_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    )
    google_email: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    refresh_token_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    last_synced_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    # ``revoked`` when Google no longer accepts the token (they disconnected
    # AloStudio from their Google account); other text: the last failure.
    last_error: str | None = Field(default=None, sa_column=Column(String, nullable=True))


class GoogleCalendarEvent(TimestampMixin, table=True):
    """The Google event made for an appointment or a CRM task, and a
    fingerprint of what was sent, so unchanged ones are not sent again."""

    __tablename__ = "google_calendar_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "source", "source_id", name="uniq_google_calendar_events_source"
        ),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    user_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    source: str = Field(sa_column=Column(String(16), nullable=False))
    source_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    event_id: str = Field(sa_column=Column(String, nullable=False))
    fingerprint: str = Field(sa_column=Column(String(64), nullable=False))


__all__ = [
    "SOURCE_ACTIVITY",
    "SOURCE_APPOINTMENT",
    "GoogleCalendarEvent",
    "GoogleCalendarLink",
]
