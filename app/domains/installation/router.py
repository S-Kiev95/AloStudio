"""``/api/v1/installation/configs`` — the settings screen's API.

Reads never return a secret in the clear, only a masked preview: the
operator needs to tell "I pasted the wrong one" from "I pasted nothing",
and nothing more. Writes are restricted to the declared registry, so the
screen can never introduce a setting the code does not read.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.installation import service
from app.domains.installation.deps import require_operator
from app.domains.installation.registry import CONFIG_SPECS, ConfigSpec, spec_for
from app.domains.installation.schemas import ConfigUpdate
from app.domains.users.models import User

router = APIRouter(prefix="/api/v1/installation", tags=["installation"])


def _spec_or_422(name: str) -> ConfigSpec:
    spec = spec_for(name)
    if spec is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"'{name}' no es una configuración conocida."},
        )
    return spec


async def _described(
    session: AsyncSession, spec: ConfigSpec
) -> dict[str, Any]:
    rows = await service.all_rows(session)
    return service.describe(spec, rows.get(spec.name))


@router.get("/configs")
async def index_configs(
    _operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Every declared setting, its effective value, and where it came
    from (database override vs environment default)."""
    rows = await service.all_rows(session)
    return {
        "payload": [
            service.describe(spec, rows.get(spec.name)) for spec in CONFIG_SPECS
        ]
    }


@router.put("/configs/{name}")
async def update_config(
    name: Annotated[str, Path()],
    payload: ConfigUpdate,
    _operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Set one setting. Takes effect in this process immediately."""
    spec = _spec_or_422(name)
    await service.set_value(session, name=name, value=payload.value)
    return await _described(session, spec)


@router.delete("/configs/{name}", status_code=status.HTTP_200_OK)
async def destroy_config(
    name: Annotated[str, Path()],
    _operator: Annotated[User, Depends(require_operator)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Remove the override so the environment default applies again."""
    spec = _spec_or_422(name)
    await service.clear_value(session, name=name)
    return await _described(session, spec)


__all__ = ["router"]
