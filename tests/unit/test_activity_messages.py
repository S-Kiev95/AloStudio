"""Unit tests for ``app.domains.conversations.activities`` content
generators.

Anchored byte-for-byte to ``reference/chatwoot/config/locales/en.yml``
(``conversations.activity.*``). If a Chatwoot upgrade rewrites a string
the test fails so the divergence is intentional.
"""

from __future__ import annotations

import pytest

from app.domains.conversations.activities import (
    assignee_change_activity_content,
    label_change_activity_content,
    mute_change_activity_content,
    priority_change_activity_content,
    status_change_activity_content,
    team_change_activity_content,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
def test_status_resolved_uses_user_name() -> None:
    assert (
        status_change_activity_content(status="resolved", user_name="Alice")
        == "Conversation was marked resolved by Alice"
    )


def test_status_open_uses_reopened_string() -> None:
    """Note: the locale uses *reopened* even though the enum value is 'open'."""
    assert (
        status_change_activity_content(status="open", user_name="Bob")
        == "Conversation was reopened by Bob"
    )


def test_status_pending() -> None:
    assert (
        status_change_activity_content(status="pending", user_name="Eve")
        == "Conversation was marked as pending by Eve"
    )


def test_status_snoozed() -> None:
    assert (
        status_change_activity_content(status="snoozed", user_name="Eve")
        == "Conversation was snoozed by Eve"
    )


def test_status_drops_when_user_missing() -> None:
    """Mirrors Rails ``user_status_change_activity_content`` returning nil
    when ``user_name`` is blank — auto-resolve and contact-resolved branches
    are deferred to Phase 6."""
    assert status_change_activity_content(status="resolved", user_name=None) is None


def test_status_unknown_value_drops() -> None:
    """An unknown status enum should never reach the generator, but if it
    does (programmer error / future Chatwoot enum value) we drop the
    activity rather than render a broken string."""
    assert (
        status_change_activity_content(status="archived", user_name="Alice")
        is None
    )


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------
def test_priority_added() -> None:
    assert (
        priority_change_activity_content(
            user_name="Alice", old_priority=None, new_priority="urgent"
        )
        == "Alice set the priority to urgent"
    )


def test_priority_updated() -> None:
    assert (
        priority_change_activity_content(
            user_name="Alice", old_priority="low", new_priority="urgent"
        )
        == "Alice changed the priority from low to urgent"
    )


def test_priority_removed() -> None:
    assert (
        priority_change_activity_content(
            user_name="Alice", old_priority="urgent", new_priority=None
        )
        == "Alice removed the priority"
    )


def test_priority_no_change_drops() -> None:
    assert (
        priority_change_activity_content(
            user_name="Alice", old_priority=None, new_priority=None
        )
        is None
    )


def test_priority_drops_when_user_missing() -> None:
    assert (
        priority_change_activity_content(
            user_name=None, old_priority=None, new_priority="urgent"
        )
        is None
    )


# ---------------------------------------------------------------------------
# Assignee
# ---------------------------------------------------------------------------
def test_assignee_self_assigned() -> None:
    assert (
        assignee_change_activity_content(
            user_name="Alice",
            assignee_name="Alice",
            self_assigned=True,
            is_assigned=True,
        )
        == "Alice self-assigned this conversation"
    )


def test_assignee_assigned_other() -> None:
    assert (
        assignee_change_activity_content(
            user_name="Alice",
            assignee_name="Bob",
            self_assigned=False,
            is_assigned=True,
        )
        == "Assigned to Bob by Alice"
    )


def test_assignee_unassigned() -> None:
    """Mirrors ``conversations.activity.assignee.removed``."""
    assert (
        assignee_change_activity_content(
            user_name="Alice",
            assignee_name=None,
            self_assigned=False,
            is_assigned=False,
        )
        == "Conversation unassigned by Alice"
    )


def test_assignee_drops_when_user_missing() -> None:
    assert (
        assignee_change_activity_content(
            user_name=None,
            assignee_name="Bob",
            self_assigned=False,
            is_assigned=True,
        )
        is None
    )


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------
def test_team_assigned_with_assignee() -> None:
    assert (
        team_change_activity_content(
            user_name="Alice",
            new_team_name="Support",
            previous_team_name=None,
            assignee_name="Bob",
            assignee_changed=True,
        )
        == "Assigned to Bob via Support by Alice"
    )


def test_team_assigned_without_assignee_change() -> None:
    """When assignee didn't change, the simpler 'Assigned to %{team_name}
    by %{user_name}' template wins (mirrors Rails' ``key`` selection)."""
    assert (
        team_change_activity_content(
            user_name="Alice",
            new_team_name="Support",
            previous_team_name=None,
            assignee_name="Bob",
            assignee_changed=False,
        )
        == "Assigned to Support by Alice"
    )


def test_team_removed_uses_previous_name() -> None:
    """``Unassigned from %{team_name}`` interpolates the OLD team — the
    new team_id is nil, so ``team.name`` would crash. Rails resolves the
    previous team via ``previous_changes[:team_id][0]``."""
    assert (
        team_change_activity_content(
            user_name="Alice",
            new_team_name=None,
            previous_team_name="Sales",
            assignee_name=None,
            assignee_changed=False,
        )
        == "Unassigned from Sales by Alice"
    )


def test_team_drops_when_user_missing() -> None:
    assert (
        team_change_activity_content(
            user_name=None,
            new_team_name="Support",
            previous_team_name=None,
            assignee_name=None,
            assignee_changed=False,
        )
        is None
    )


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
def test_label_added_single() -> None:
    assert (
        label_change_activity_content(
            user_name="Alice", change_type="added", labels=["urgent"]
        )
        == "Alice added urgent"
    )


def test_label_added_multiple_joined_with_comma_space() -> None:
    """Mirrors Rails ``labels: labels.join(', ')``."""
    assert (
        label_change_activity_content(
            user_name="Alice",
            change_type="added",
            labels=["urgent", "billing"],
        )
        == "Alice added urgent, billing"
    )


def test_label_removed() -> None:
    assert (
        label_change_activity_content(
            user_name="Bob", change_type="removed", labels=["urgent"]
        )
        == "Bob removed urgent"
    )


def test_label_empty_diff_drops() -> None:
    """Mirrors ``return unless labels.size.positive?``."""
    assert (
        label_change_activity_content(
            user_name="Alice", change_type="added", labels=[]
        )
        is None
    )


def test_label_drops_when_user_missing() -> None:
    assert (
        label_change_activity_content(
            user_name=None, change_type="added", labels=["urgent"]
        )
        is None
    )


def test_label_unknown_change_type_drops() -> None:
    """Defensive: if a future caller passes a typo'd change_type we drop
    rather than render a broken string."""
    assert (
        label_change_activity_content(
            user_name="Alice", change_type="updated", labels=["urgent"]
        )
        is None
    )


# ---------------------------------------------------------------------------
# Mute
# ---------------------------------------------------------------------------
def test_mute_muted() -> None:
    assert (
        mute_change_activity_content(user_name="Alice", change_type="muted")
        == "Alice has muted the conversation"
    )


def test_mute_unmuted() -> None:
    assert (
        mute_change_activity_content(
            user_name="Alice", change_type="unmuted"
        )
        == "Alice has unmuted the conversation"
    )


def test_mute_drops_when_user_missing() -> None:
    """Mirrors ``return unless Current.user``."""
    assert (
        mute_change_activity_content(user_name=None, change_type="muted")
        is None
    )
