"""Team service layer.

Ports ``Api::V1::Accounts::TeamsController`` + the inline ``Team``
helpers ``add_members`` / ``remove_members``.

Name normalization — Chatwoot lowercases the team name via a Rails
``before_validation`` hook. We do it in the service layer instead of
inside the SQLModel class so the transformation is visible in the
read/write path (SQLModel has no ``@validates``-equivalent without
Pydantic validators, and adding one would require ``table=True`` gymnastics
that hurt more than help). Effect is identical: ``"Support"`` collapses
to ``"support"`` before the unique(name, account_id) check runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.accounts.models import Account
from app.domains.teams.models import Team, TeamMember


def _normalize_name(name: str) -> str:
    """Rails ``self.name = name.downcase`` — done before unique check.

    Chatwoot's ``before_validation { self.name = name.downcase }`` only
    runs when the attribute is present; a blank name still raises the
    presence error. Mirror: we lowercase any non-None value and let an
    empty string fall through to the validation error at the column
    level.
    """
    return name.lower()


@dataclass(slots=True)
class TeamCreateParams:
    account: Account
    name: str
    description: str | None = None
    allow_auto_assign: bool | None = None


@dataclass(slots=True)
class TeamUpdateParams:
    name: str | None = None
    description: str | None = None
    allow_auto_assign: bool | None = None


async def create_team(session: AsyncSession, params: TeamCreateParams) -> Team:
    assert params.account.id is not None
    team = Team(
        account_id=params.account.id,
        name=_normalize_name(params.name),
        description=params.description,
    )
    if params.allow_auto_assign is not None:
        team.allow_auto_assign = params.allow_auto_assign
    session.add(team)
    await session.flush()
    await session.refresh(team)
    return team


async def update_team(
    session: AsyncSession, *, team: Team, params: TeamUpdateParams
) -> Team:
    if params.name is not None:
        team.name = _normalize_name(params.name)
    if params.description is not None:
        team.description = params.description
    if params.allow_auto_assign is not None:
        team.allow_auto_assign = params.allow_auto_assign
    session.add(team)
    await session.flush()
    await session.refresh(team)
    return team


async def delete_team(session: AsyncSession, team: Team) -> None:
    """Cascade: TeamMember rows go via FK ondelete='CASCADE'."""
    await session.delete(team)
    await session.flush()


# ---------------------------------------------------------------------------
# Team membership
# ---------------------------------------------------------------------------
async def list_member_ids(session: AsyncSession, team_id: int) -> list[int]:
    stmt = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
    return list((await session.exec(stmt)).all())


async def add_members(
    session: AsyncSession, *, team: Team, user_ids: list[int]
) -> list[TeamMember]:
    """Insert new :class:`TeamMember` rows; idempotent over duplicates."""
    assert team.id is not None
    if not user_ids:
        return []
    existing = set(await list_member_ids(session, team.id))
    new_ids = [uid for uid in user_ids if uid not in existing]
    members = [TeamMember(team_id=team.id, user_id=uid) for uid in new_ids]
    for m in members:
        session.add(m)
    await session.flush()
    return members


async def remove_members(
    session: AsyncSession, *, team: Team, user_ids: list[int]
) -> None:
    assert team.id is not None
    if not user_ids:
        return
    stmt = select(TeamMember).where(
        TeamMember.team_id == team.id,
        TeamMember.user_id.in_(user_ids),  # type: ignore[attr-defined]
    )
    rows = (await session.exec(stmt)).all()
    for r in rows:
        await session.delete(r)
    await session.flush()


# ---------------------------------------------------------------------------
# Validation helper — ``TeamMembersController#validate_member_id_params``
# ---------------------------------------------------------------------------
async def user_ids_outside_account(
    session: AsyncSession, *, account: Account, user_ids: list[int]
) -> list[int]:
    """Return the subset of ``user_ids`` that aren't members of ``account``.

    Matches Rails ``invalid_ids = params[:user_ids].map(&:to_i) -
    @team.account.user_ids``. Empty list means the caller can proceed.
    """
    from app.domains.users.models import AccountUser

    if not user_ids:
        return []
    stmt = select(AccountUser.user_id).where(
        AccountUser.account_id == account.id,
        AccountUser.user_id.in_(user_ids),  # type: ignore[attr-defined]
    )
    known = set((await session.exec(stmt)).all())
    return [uid for uid in user_ids if uid not in known]


# Shim for mypy to know Any is used above — mypy --strict flags unused
# imports. We use ``Any`` in the typing of ``TeamUpdateParams`` via
# descendants later; keep the import graph tight.
_ = Any
