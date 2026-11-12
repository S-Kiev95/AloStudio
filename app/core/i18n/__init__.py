"""Texts the backend sends to people — system mail, notification mail and
web-push — in the language each person chose (F13).

The language is the one picked in Ajustes → Mi perfil → Idioma, saved in
``users.ui_settings["locale"]`` (the same value the dashboard uses).
Spanish is the source and the fallback: a missing key, an unknown language,
or someone who never chose one all get Spanish.

Catalogs live next to this file, one module per language, as a flat dict of
dotted keys. ``{name}`` in a text is filled from the keyword arguments of
:func:`t`. ``tests/unit/test_i18n_catalogs.py`` checks every language has the
same keys and the same ``{placeholders}`` as Spanish.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.i18n import de, en, es, fr, ja, ko, pt

LOCALES: tuple[str, ...] = ("es", "en", "pt", "fr", "de", "ja", "ko")
DEFAULT_LOCALE = "es"

CATALOGS: dict[str, dict[str, str]] = {
    "es": es.MESSAGES,
    "en": en.MESSAGES,
    "pt": pt.MESSAGES,
    "fr": fr.MESSAGES,
    "de": de.MESSAGES,
    "ja": ja.MESSAGES,
    "ko": ko.MESSAGES,
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def normalize_locale(value: object) -> str:
    """A supported language code, or Spanish. Accepts ``"pt-BR"`` and the
    like by its base language."""
    if isinstance(value, str):
        base = value.strip().lower().replace("_", "-").split("-")[0]
        if base in CATALOGS:
            return base
    return DEFAULT_LOCALE


def user_locale(user: Any) -> str:
    """The language a user chose in their profile (Spanish if none)."""
    settings = getattr(user, "ui_settings", None) or {}
    return normalize_locale(settings.get("locale") if isinstance(settings, dict) else None)


def has_locale(user: Any) -> bool:
    """Whether the user ever chose a language (vs. falling back to Spanish)."""
    settings = getattr(user, "ui_settings", None) or {}
    return isinstance(settings, dict) and settings.get("locale") in CATALOGS


def t(locale: str, key: str, **values: Any) -> str:
    """The text for ``key`` in ``locale``, with ``{name}`` filled in."""
    text = CATALOGS.get(locale, {}).get(key) or CATALOGS[DEFAULT_LOCALE].get(key, key)
    if not values:
        return text
    return _PLACEHOLDER.sub(
        lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text
    )


def mail_text(locale: str, *, name: str, body: str) -> str:
    """A plain-text mail: greeting, body and sign-off, in ``locale``."""
    return (
        f"{t(locale, 'mail.greeting', name=name)}\n\n{body}\n\n{t(locale, 'mail.signoff')}\n"
    )


def placeholders(text: str) -> set[str]:
    return set(_PLACEHOLDER.findall(text))


__all__ = [
    "CATALOGS",
    "DEFAULT_LOCALE",
    "LOCALES",
    "has_locale",
    "mail_text",
    "normalize_locale",
    "placeholders",
    "t",
    "user_locale",
]
