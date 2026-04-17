from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin(SQLModel):
    """Mirrors Rails' `timestamps` — created_at / updated_at, UTC, timezone-aware."""

    created_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now(), "nullable": False},
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": func.now(),
            "nullable": False,
        },
    )
