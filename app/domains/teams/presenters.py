"""Team response shaping — ports ``_team.json.jbuilder`` + ``team_members`` views.

Chatwoot's per-row team payload:

  {
    "id": 1,
    "name": "support",
    "description": "...",
    "allow_auto_assign": true,
    "account_id": 7,
    "is_member": true
  }

``is_member`` flags whether the calling user is on the team, via
``Current.user.teams.include?(resource)``. We pass it in explicitly so the
presenter stays free of DB access — the router precomputes the set of
team_ids the caller belongs to and probes it per row (O(1) dict lookup).

Unlike inboxes, the teams index does **not** wrap in ``{"payload": [...]}``:
``teams/index.json.jbuilder`` uses ``json.array!`` directly, which emits a
top-level JSON array. Same for team_members. Keep this distinction — a
naive wrapper would break parity.
"""

from __future__ import annotations

from typing import Any

from app.domains.teams.models import Team


def present_team(team: Team, *, is_member: bool) -> dict[str, Any]:
    """Emit one team row in Chatwoot wire shape."""
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "allow_auto_assign": team.allow_auto_assign,
        "account_id": team.account_id,
        "is_member": is_member,
    }


def present_teams_index(
    teams: list[Team], *, member_team_ids: set[int]
) -> list[dict[str, Any]]:
    """Top-level JSON array — no envelope. ``member_team_ids`` holds the
    caller's team ids so ``is_member`` resolves with one set lookup per row.
    """
    return [
        present_team(t, is_member=(t.id in member_team_ids if t.id is not None else False))
        for t in teams
    ]
