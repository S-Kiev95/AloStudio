"""Reading and writing installation config, and pushing it into Settings.

The environment stays the source of defaults; a row in
``installation_configs`` overrides one. That ordering is deliberate — a
deployment starts with nothing configured and works, and the operator
fills settings in from the dashboard as they get them, without ever
editing a file on the server.

Freshness across processes: the API and the ARQ worker each hold their
own ``Settings``, so a write in one is not instantly visible in the
other. Each process refreshes on a timer (see :func:`refresh_if_stale`),
and the process that performs a write refreshes immediately, so the
operator always sees their own change take effect at once.
"""

from __future__ import annotations

import time
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import clear_settings_overlay, get_settings, set_settings_overlay
from app.core.errors import ChatwootHTTPException
from app.domains.installation.models import InstallationConfig
from app.domains.installation.registry import CONFIG_SPECS, ConfigSpec, spec_for

# How long a process may serve a stale overlay. Config changes are rare;
# a short window costs a query per interval per process.
REFRESH_INTERVAL_SECONDS = 20.0

_last_loaded_at: float | None = None


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
async def all_rows(session: AsyncSession) -> dict[str, InstallationConfig]:
    rows = (await session.exec(select(InstallationConfig))).all()
    return {row.name: row for row in rows}


async def load_overlay(session: AsyncSession) -> dict[str, Any]:
    """Read every declared config out of the DB into a Settings overlay.

    Undeclared rows are ignored: the registry decides what may reach
    ``Settings``, so a stray row can never inject a setting.
    """
    rows = await all_rows(session)
    overlay: dict[str, Any] = {}
    for spec in CONFIG_SPECS:
        row = rows.get(spec.name)
        if row is None:
            continue
        overlay[spec.setting] = _coerce(spec, row.value)
    return overlay


async def apply_overlay(session: AsyncSession) -> dict[str, Any]:
    """Load the DB config and make ``get_settings()`` return it."""
    global _last_loaded_at
    overlay = await load_overlay(session)
    set_settings_overlay(overlay)
    _last_loaded_at = time.monotonic()
    return overlay


async def refresh_if_stale(session: AsyncSession) -> bool:
    """Re-read the overlay when the last load aged out. True if it ran."""
    if (
        _last_loaded_at is not None
        and time.monotonic() - _last_loaded_at < REFRESH_INTERVAL_SECONDS
    ):
        return False
    await apply_overlay(session)
    return True


def reset_overlay() -> None:
    """Drop the overlay entirely — back to pure environment. For tests."""
    global _last_loaded_at
    clear_settings_overlay()
    _last_loaded_at = None


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
async def set_value(
    session: AsyncSession, *, name: str, value: Any
) -> InstallationConfig:
    """Upsert one declared, unlocked config and refresh this process.

    An unknown or locked name is a 422 rather than a silent no-op: the
    dashboard should never be able to write a key the code won't read.
    """
    spec = spec_for(name)
    if spec is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"'{name}' no es una configuración conocida."},
        )

    row = (
        await session.exec(
            select(InstallationConfig).where(InstallationConfig.name == name)
        )
    ).first()
    if row is not None and row.locked:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"'{name}' está bloqueada y no se edita desde el panel."
                )
            },
        )

    coerced = _coerce(spec, value)
    if row is None:
        row = InstallationConfig(
            name=name, serialized_value={"value": coerced}, locked=False
        )
    else:
        row.serialized_value = {"value": coerced}
    session.add(row)
    await session.flush()
    await apply_overlay(session)
    return row


async def clear_value(session: AsyncSession, *, name: str) -> None:
    """Delete the override so the environment default applies again."""
    row = (
        await session.exec(
            select(InstallationConfig).where(InstallationConfig.name == name)
        )
    ).first()
    if row is None:
        return
    if row.locked:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"'{name}' está bloqueada."},
        )
    await session.delete(row)
    await session.flush()
    await apply_overlay(session)


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------
def mask(value: Any) -> str:
    """A secret's shape without the secret.

    Enough to tell "I pasted the wrong one" from "I pasted nothing",
    which is the only thing an operator needs to see.
    """
    text = "" if value is None else str(value)
    if not text:
        return ""
    if len(text) <= 8:
        return "•" * len(text)
    return f"{text[:3]}{'•' * 6}{text[-2:]}"


def describe(spec: ConfigSpec, row: InstallationConfig | None) -> dict[str, Any]:
    """One config as the dashboard sees it — never a secret in the clear."""
    effective = getattr(get_settings(), spec.setting, None)
    configured = bool(effective) if spec.kind != "boolean" else True
    if spec.secret:
        shown: Any = mask(effective)
    else:
        shown = effective
    return {
        "name": spec.name,
        "title": spec.title,
        "description": spec.description,
        "group": spec.group,
        "kind": spec.kind,
        "secret": spec.secret,
        "value": shown,
        "configured": configured,
        # Where the effective value came from, so "I set that and it
        # didn't change" has an answer.
        "source": "database" if row is not None else "environment",
        "editable": row is None or not row.locked,
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _coerce(spec: ConfigSpec, value: Any) -> Any:
    """Bring a JSON value to the type the ``Settings`` field expects."""
    if spec.kind == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "t", "yes", "on"}
    return "" if value is None else str(value).strip()


__all__ = [
    "REFRESH_INTERVAL_SECONDS",
    "apply_overlay",
    "clear_value",
    "describe",
    "load_overlay",
    "mask",
    "refresh_if_stale",
    "reset_overlay",
    "set_value",
]
