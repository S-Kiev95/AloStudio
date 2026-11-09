"""Pydantic schemas for the notifications surface."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, field_validator


class NotificationSettingsUpdate(BaseModel):
    """``PATCH /notification_settings`` — every field optional.

    ``whatsapp_number`` is normalised to digits only (country code
    included); an empty string clears it.
    """

    model_config = ConfigDict(extra="ignore")

    selected_email_flags: list[str] | None = None
    selected_push_flags: list[str] | None = None
    selected_whatsapp_flags: list[str] | None = None
    whatsapp_number: str | None = None

    @field_validator("whatsapp_number")
    @classmethod
    def _normalise_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = re.sub(r"[\s()+.-]", "", value)
        if digits == "":
            return ""
        if not re.fullmatch(r"\d{8,15}", digits):
            raise ValueError(
                "El número tiene que incluir el código de país, solo dígitos "
                "(por ejemplo 59899123456)."
            )
        return digits


__all__ = ["NotificationSettingsUpdate"]
