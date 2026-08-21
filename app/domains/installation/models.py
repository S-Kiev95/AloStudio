"""The ``installation_configs`` table.

Schema mirrors Chatwoot's so a future data migration is a straight copy:
``name`` unique, the value wrapped in a ``serialized_value`` JSONB object
under a ``value`` key, and a ``locked`` flag for configs the dashboard
must not expose.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.core.base_model import TimestampMixin


class InstallationConfig(TimestampMixin, SQLModel, table=True):
    """One installation-wide setting.

    The value is wrapped rather than stored bare because JSONB has no way
    to hold a top-level ``null`` distinguishably from SQL NULL, and
    "explicitly set to empty" has to differ from "never set" — the first
    overrides the environment, the second falls back to it.
    """

    __tablename__ = "installation_configs"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(
        sa_column=Column(String, nullable=False, unique=True, index=True)
    )
    serialized_value: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    # Locked configs are readable by the code but never editable from the
    # dashboard — Chatwoot's default, and the safe one.
    locked: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )

    @property
    def value(self) -> Any:
        return (self.serialized_value or {}).get("value")


__all__ = ["InstallationConfig"]
