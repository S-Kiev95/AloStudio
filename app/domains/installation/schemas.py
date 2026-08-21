"""Request bodies for the installation-config API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    """One setting's new value.

    Deliberately ``Any``: the registry declares the type and the service
    coerces to it, so a checkbox can send ``true`` and a text field a
    string without two endpoints.
    """

    value: Any = None


__all__ = ["ConfigUpdate"]
