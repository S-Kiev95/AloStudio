"""Team + team_members HTTP endpoints.

Ports ``Api::V1::Accounts::TeamsController`` +
``Api::V1::Accounts::TeamMembersController``.

Route map (Chatwoot):

  * ``GET    /api/v1/accounts/:account_id/teams``
  * ``POST   /api/v1/accounts/:account_id/teams``
  * ``GET    /api/v1/accounts/:account_id/teams/:id``
  * ``PATCH  /api/v1/accounts/:account_id/teams/:id``
  * ``DELETE /api/v1/accounts/:account_id/teams/:id``
  * ``GET    /api/v1/accounts/:account_id/teams/:team_id/team_members``
  * ``POST   /api/v1/accounts/:account_id/teams/:team_id/team_members``
  * ``PATCH  /api/v1/accounts/:account_id/teams/:team_id/team_members``
  * ``DELETE /api/v1/accounts/:account_id/teams/:team_id/team_members``

Authorisation (:class:`TeamPolicy`):

  * ``index?`` / ``show?`` → any account member
  * ``create?`` / ``update?`` / ``destroy?`` → administrator

``TeamMemberPolicy`` doesn't exist in Chatwoot — ``TeamMembersController``
uses ``check_authorization`` against ``TeamPolicy`` via the controller's
resource. Effect: add/remove/list also goes through the team's policy.
For us that means index/show → any member, mutations → admin.

Delete returns ``head :ok`` (empty 200). The destroy_async in Rails is
replaced by a synchronous cascade through the FK; wire-visible behaviour
is identical.

Unique-name violation (409 on the DB) is mapped to Chatwoot's 422
``{"message": "Name has already been taken"}`` — Rails' presence +
uniqueness validators converge on this shape because
``ActiveRecord::RecordInvalid`` is rendered by
``RequestExceptionHandler`` as ``{"message": exception.record.errors.full_messages.join(', ')}``
with status 422.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import (
    AccountContext,
    account_context,
    require_admin,
)
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.presenters import present_agent
from app.domains.teams.models import Team, TeamMember
from app.domains.teams.presenters import present_team, present_teams_index
from app.domains.teams.schemas import (
    TeamCreateRequest,
    TeamMembersBody,
    TeamUpdateRequest,
)
from app.domains.teams.service import (
    TeamCreateParams,
    TeamUpdateParams,
    add_members,
    create_team,
    delete_team,
    list_member_ids,
    remove_members,
    update_team,
    user_ids_outside_account,
)
from app.domains.users.models import AccountUser, User

router = APIRouter(prefix="/api/v1/accounts/{account_id}/teams", tags=["teams"])

# Nested route under ``teams/:team_id`` — sibling router to keep the
# FastAPI path hierarchy readable.
team_members_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/teams/{team_id}/team_members",
    tags=["teams"],
)


# ============================================================================
# Teams CRUD
# ============================================================================
@router.get("")
async def list_teams(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    """``GET /api/v1/accounts/:account_id/teams`` — list all teams.

    Chatwoot returns the full account-scoped set regardless of caller
    role. ``is_member`` per row tells the UI which teams the caller
    belongs to.
    """
    assert ctx.account.id is not None
    teams_stmt = (
        select(Team)
        .where(Team.account_id == ctx.account.id)
        .order_by(Team.name, Team.id)  # type: ignore[arg-type]
    )
    teams = list((await session.exec(teams_stmt)).all())
    member_ids = await _team_ids_for_user(session, user_id=ctx.user.id, account_id=ctx.account.id)  # type: ignore[arg-type]
    return present_teams_index(teams, member_team_ids=member_ids)


@router.post("", status_code=status.HTTP_200_OK)
async def create_team_endpoint(
    payload: TeamCreateRequest,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``POST /api/v1/accounts/:account_id/teams`` — admin-only.

    Chatwoot returns 200 on create (``render action: 'create'`` →
    ``create.json.jbuilder`` → the team partial). Match exactly.
    """
    try:
        team = await create_team(
            session,
            TeamCreateParams(
                account=ctx.account,
                name=payload.name,
                description=payload.description,
                allow_auto_assign=payload.allow_auto_assign,
            ),
        )
    except IntegrityError as exc:
        _raise_name_taken(exc)
    # Creator isn't automatically a member (Rails doesn't auto-join).
    return present_team(team, is_member=False)


@router.get("/{team_id}")
async def show_team(
    team_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``GET /api/v1/accounts/:account_id/teams/:id`` — any member."""
    team = await _find_team_in_account(session, ctx, team_id)
    is_member = await _user_on_team(session, user_id=ctx.user.id, team_id=team_id)  # type: ignore[arg-type]
    return present_team(team, is_member=is_member)


@router.patch("/{team_id}")
async def update_team_endpoint(
    team_id: Annotated[int, Path()],
    payload: TeamUpdateRequest,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``PATCH /api/v1/accounts/:account_id/teams/:id`` — admin-only."""
    team = await _find_team_in_account(session, ctx, team_id)
    try:
        updated = await update_team(
            session,
            team=team,
            params=TeamUpdateParams(
                name=payload.name,
                description=payload.description,
                allow_auto_assign=payload.allow_auto_assign,
            ),
        )
    except IntegrityError as exc:
        _raise_name_taken(exc)
    is_member = await _user_on_team(session, user_id=ctx.user.id, team_id=team_id)  # type: ignore[arg-type]
    return present_team(updated, is_member=is_member)


@router.delete("/{team_id}", status_code=status.HTTP_200_OK)
async def destroy_team(
    team_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``DELETE /api/v1/accounts/:account_id/teams/:id`` — admin-only.

    Chatwoot: ``@team.destroy!; head :ok``. Empty body, 200. FK cascade
    takes care of the ``team_members`` rows.
    """
    team = await _find_team_in_account(session, ctx, team_id)
    await delete_team(session, team)
    return {}


# ============================================================================
# TeamMembers
# ============================================================================
@team_members_router.get("")
async def list_team_members(
    team_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    """``GET …/teams/:team_id/team_members`` — list member agents.

    Chatwoot returns a top-level JSON array of agents (not wrapped). The
    ``_agent.json.jbuilder`` partial is shared with inbox_members; we
    reuse :func:`present_agent` from the inbox presenters module.
    """
    team = await _find_team_in_account(session, ctx, team_id)
    return await _fetch_agents_payload(session, ctx, team)


@team_members_router.post("", status_code=status.HTTP_200_OK)
async def create_team_members(
    team_id: Annotated[int, Path()],
    payload: TeamMembersBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    """``POST …/team_members`` — add agents.

    Chatwoot:

        def create
          ActiveRecord::Base.transaction do
            @team_members = @team.add_members(members_to_be_added_ids)
          end
        end

    ``members_to_be_added_ids`` filters out already-current members. Our
    service-layer :func:`~app.domains.teams.service.add_members` already
    de-dupes, so we pass the raw list.

    ``validate_member_id_params`` rejects user_ids that aren't members of
    the account with ``{"error": "Invalid User IDs"}`` / 401.
    """
    team = await _find_team_in_account(session, ctx, team_id)
    await _validate_user_ids(session, ctx, payload.user_ids)
    await add_members(session, team=team, user_ids=payload.user_ids)
    return await _fetch_agents_payload(session, ctx, team)


@team_members_router.patch("", status_code=status.HTTP_200_OK)
async def update_team_members(
    team_id: Annotated[int, Path()],
    payload: TeamMembersBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    """``PATCH …/team_members`` — replace the agent set (add new, drop missing)."""
    team = await _find_team_in_account(session, ctx, team_id)
    await _validate_user_ids(session, ctx, payload.user_ids)
    assert team.id is not None
    current = set(await list_member_ids(session, team.id))
    desired = set(payload.user_ids)
    to_add = sorted(desired - current)
    to_remove = sorted(current - desired)
    await add_members(session, team=team, user_ids=to_add)
    await remove_members(session, team=team, user_ids=to_remove)
    return await _fetch_agents_payload(session, ctx, team)


@team_members_router.delete("", status_code=status.HTTP_200_OK)
async def destroy_team_members(
    team_id: Annotated[int, Path()],
    payload: TeamMembersBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``DELETE …/team_members`` — remove listed agents.

    Chatwoot: ``head :ok`` (empty 200). The destroy action also runs
    ``validate_member_id_params`` — a DELETE with user_ids outside the
    account still 401s.
    """
    team = await _find_team_in_account(session, ctx, team_id)
    await _validate_user_ids(session, ctx, payload.user_ids)
    await remove_members(session, team=team, user_ids=payload.user_ids)
    return {}


# ============================================================================
# helpers
# ============================================================================
async def _find_team_in_account(
    session: AsyncSession, ctx: AccountContext, team_id: int
) -> Team:
    """Account-scoped lookup. 404 on miss (Rails' ``.find`` raises)."""
    stmt = select(Team).where(Team.id == team_id, Team.account_id == ctx.account.id)
    team = (await session.exec(stmt)).first()
    if team is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return team


async def _user_on_team(session: AsyncSession, *, user_id: int, team_id: int) -> bool:
    """One-row membership probe — for ``is_member`` on show endpoints."""
    stmt = select(TeamMember.id).where(
        TeamMember.team_id == team_id, TeamMember.user_id == user_id
    )
    return (await session.exec(stmt)).first() is not None


async def _team_ids_for_user(
    session: AsyncSession, *, user_id: int, account_id: int
) -> set[int]:
    """Return the set of team_ids ``user_id`` belongs to within the account.

    Used by the index endpoint so ``is_member`` is an O(1) set lookup
    per row instead of N+1.
    """
    stmt = (
        select(TeamMember.team_id)
        .join(Team, Team.id == TeamMember.team_id)  # type: ignore[arg-type]
        .where(TeamMember.user_id == user_id, Team.account_id == account_id)
    )
    return set((await session.exec(stmt)).all())


async def _validate_user_ids(
    session: AsyncSession, ctx: AccountContext, user_ids: list[int]
) -> None:
    """Mirror ``TeamMembersController#validate_member_id_params``.

    Invalid ids → 401 ``{"error": "Invalid User IDs"}``. Empty list is
    a no-op (Rails also short-circuits when there's nothing to validate
    against ``account.user_ids``).
    """
    invalid = await user_ids_outside_account(
        session, account=ctx.account, user_ids=user_ids
    )
    if invalid:
        raise ChatwootHTTPException(
            status_code=401,
            detail={"error": "Invalid User IDs"},
        )


async def _fetch_agents_payload(
    session: AsyncSession, ctx: AccountContext, team: Team
) -> list[dict]:
    """Top-level JSON array of agents — Chatwoot's ``team_members`` shape.

    Unlike inbox_members (``{"payload": [...]}``), team_members uses
    ``json.array!`` so the body is a raw array at the root.
    """
    assert team.id is not None and ctx.account.id is not None
    stmt = (
        select(User, AccountUser)
        .join(TeamMember, TeamMember.user_id == User.id)  # type: ignore[arg-type]
        .join(
            AccountUser,
            (AccountUser.user_id == User.id) & (AccountUser.account_id == ctx.account.id),  # type: ignore[arg-type]
        )
        .where(TeamMember.team_id == team.id)
        .order_by(User.name, User.id)  # type: ignore[arg-type]
    )
    rows = (await session.exec(stmt)).all()
    return [
        present_agent(
            account_id=ctx.account.id,
            account_user_availability=au.availability,
            account_user_auto_offline=au.auto_offline,
            user=u,
        )
        for (u, au) in rows
    ]


def _raise_name_taken(exc: IntegrityError) -> None:
    """Map a unique-constraint violation on (name, account_id) to
    Chatwoot's ``RecordInvalid`` wire body.

    The Rails error message is ``"Name has already been taken"`` —
    produced by ``ActiveModel::Errors`` from the ``validates :name,
    uniqueness: {scope: :account_id}`` rule. We raise the same string
    so parity tests diff empty.
    """
    # We could sniff ``exc.orig`` for the constraint name to be more
    # defensive, but this is the only uniqueness rule on the table —
    # any IntegrityError here is the name clash.
    _ = exc
    raise ChatwootHTTPException(
        status_code=422,
        detail={"message": "Name has already been taken"},
    )
