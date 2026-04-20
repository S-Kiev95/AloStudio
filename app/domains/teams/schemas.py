"""Request bodies for the teams + team_members endpoints.

Ports ``Api::V1::Accounts::TeamsController#team_params`` and
``Api::V1::Accounts::TeamMembersController``.

Rails' ``params.require(:team).permit(:name, :description, :allow_auto_assign)``
is the shape for POST/PUT bodies. With the Rails default of
``wrap_parameters :json`` on, callers send a flat JSON hash
(``{"name": "Support"}``) and Rails auto-wraps it as ``{team: {name:...}}``
server-side. We skip the wrapping and read the flat body directly — same
wire behaviour from a client's perspective.

``extra="ignore"`` mirrors Rails' strong-params: unknown keys are silently
dropped, never 422'd.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# POST / PATCH /api/v1/accounts/:id/teams
# ---------------------------------------------------------------------------
class TeamCreateRequest(BaseModel):
    """``team_params`` on POST.

    ``name`` is required by Rails' presence validation. ``allow_auto_assign``
    defaults to ``true`` in the DB; Pydantic leaves it ``None`` and the
    service layer honours the column default when we don't set it.
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    description: str | None = None
    allow_auto_assign: bool | None = None


class TeamUpdateRequest(BaseModel):
    """``team_params`` on PATCH — all optional."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    allow_auto_assign: bool | None = None


# ---------------------------------------------------------------------------
# team_members endpoints
# ---------------------------------------------------------------------------
class TeamMembersBody(BaseModel):
    """Body for POST/PATCH/DELETE ``/team_members``.

    Chatwoot's ``TeamMembersController`` accepts ``user_ids: [1, 2, 3]`` on
    all three verbs. The ``team_id`` field appears in some Chatwoot client
    payloads but the controller always trusts the path param; we do the
    same.
    """

    model_config = ConfigDict(extra="ignore")

    team_id: int | None = None  # accepted for parity; path param wins
    user_ids: list[int]
