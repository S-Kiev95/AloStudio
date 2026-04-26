"""Unit tests for ``app.domains.conversations.listeners``.

Goals:
  * Pin the event-name -> handler routing (so renaming a constant +
    forgetting the handler dict is a loud failure).
  * Verify ``_broadcast`` merges ``account_id`` and the optional
    ``performer`` block onto every payload — the two non-trivial
    invariants the Ruby listener enforces.
  * Verify the message-created path drops contact tokens for private
    + activity messages (Chatwoot's ``contact_tokens(...)`` guard).

We patch the broadcaster to a recording stub. Token-resolution queries
that hit the DB are out of scope for unit tests — the listener is given
already-loaded relationships via SimpleNamespace, and the SQL helpers
``_inbox_member_tokens`` / ``_administrator_tokens`` /
``_contact_inbox_tokens`` are stubbed out per-test. Integration tests
in 4b.6 exercise the full DB path.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.domains.conversations import events as ev
from app.domains.conversations.listeners import (
    ActionCableListener,
    _HANDLERS,
)
from app.domains.conversations.models import (
    MESSAGE_TYPE_ACTIVITY,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Recording broadcaster — the surface ``ActionCableListener`` uses.
# ---------------------------------------------------------------------------
class _RecBroadcaster:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str, dict[str, Any]]] = []

    async def publish(
        self, channels: Any, event: str, data: dict[str, Any]
    ) -> int:
        chan_list = sorted(c for c in channels if c)
        self.calls.append((chan_list, event, data))
        return len(chan_list)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def test_handler_dict_covers_4b_subset() -> None:
    """Pin the active handler set across 4b.

    4b.1 added five events, 4b.5 added the two ``typing_*`` events.
    If the dict drifts from this set the test fails so the divergence
    is intentional.
    """
    assert set(_HANDLERS.keys()) == {
        ev.CONVERSATION_CREATED,
        ev.CONVERSATION_UPDATED,
        ev.CONVERSATION_STATUS_CHANGED,
        ev.CONVERSATION_TYPING_ON,
        ev.CONVERSATION_TYPING_OFF,
        ev.MESSAGE_CREATED,
        ev.FIRST_REPLY_CREATED,
    }


async def test_dispatch_unknown_event_is_a_noop() -> None:
    """Mirrors Rails' listener silently ignoring methods it doesn't
    declare. Unknown events must NOT raise — the dispatcher fans out
    indiscriminately and other listeners would be broken otherwise.
    """
    bc = _RecBroadcaster()
    listener = ActionCableListener(session=None, broadcaster=bc, performer=None)  # type: ignore[arg-type]
    await listener.dispatch("absolutely.unknown.event", x=1)
    assert bc.calls == []


async def test_dispatch_swallows_handler_exceptions() -> None:
    """A broken listener must NEVER bubble — the request-cycle would
    fail mid-success otherwise."""
    bc = _RecBroadcaster()
    listener = ActionCableListener(session=None, broadcaster=bc, performer=None)  # type: ignore[arg-type]

    # Force the message_created handler to raise by passing a message
    # whose ``conversation`` lookup blows up.
    class _BadMessage:
        @property
        def conversation(self) -> Any:
            raise RuntimeError("boom")

    await listener.dispatch(ev.MESSAGE_CREATED, message=_BadMessage())
    assert bc.calls == []  # nothing published, but no exception leaked


# ---------------------------------------------------------------------------
# _broadcast invariants
# ---------------------------------------------------------------------------
async def test_broadcast_merges_account_id() -> None:
    bc = _RecBroadcaster()
    listener = ActionCableListener(session=None, broadcaster=bc)  # type: ignore[arg-type]

    await listener._broadcast(
        account_id=42,
        tokens=["t1", "t2"],
        event_name=ev.CONVERSATION_CREATED,
        data={"id": 7, "status": "open"},
    )

    assert len(bc.calls) == 1
    channels, event, payload = bc.calls[0]
    assert channels == ["t1", "t2"]
    assert event == ev.CONVERSATION_CREATED
    assert payload == {"id": 7, "status": "open", "account_id": 42}


async def test_broadcast_includes_performer_when_set() -> None:
    """Mirrors Rails' ``payload[:performer] = Current.user.push_event_data
    if Current.user.present?``.
    """
    bc = _RecBroadcaster()
    performer = SimpleNamespace(id=99, name="Alice", display_name="Alice A.")
    listener = ActionCableListener(session=None, broadcaster=bc, performer=performer)  # type: ignore[arg-type]

    await listener._broadcast(
        account_id=1,
        tokens=["t1"],
        event_name=ev.CONVERSATION_UPDATED,
        data={"id": 1},
    )

    payload = bc.calls[0][2]
    assert payload["performer"]["id"] == 99
    assert payload["performer"]["name"] == "Alice"
    assert payload["performer"]["type"] == "user"


async def test_broadcast_skips_empty_token_list() -> None:
    """Mirrors Rails ``return if tokens.blank?``. The broadcaster also
    drops empty channel lists, but the listener short-circuits earlier."""
    bc = _RecBroadcaster()
    listener = ActionCableListener(session=None, broadcaster=bc)  # type: ignore[arg-type]

    await listener._broadcast(
        account_id=1, tokens=[], event_name=ev.MESSAGE_CREATED, data={"id": 1}
    )
    assert bc.calls == []


# ---------------------------------------------------------------------------
# message_created — private + activity guards on contact_tokens.
# ---------------------------------------------------------------------------
async def _stub_token_resolvers(
    listener: ActionCableListener,
    *,
    user_tokens: list[str],
    contact_inbox_tokens: list[str],
) -> None:
    """Replace the two DB-touching helpers with fixtures."""

    async def _user_tokens(_conv: Any) -> list[str]:
        return user_tokens

    async def _contact_inbox_tokens(_ci: Any) -> list[str]:
        return contact_inbox_tokens

    listener._user_tokens = _user_tokens  # type: ignore[method-assign]
    listener._contact_inbox_tokens = _contact_inbox_tokens  # type: ignore[method-assign]


async def test_message_created_excludes_contact_for_private_message() -> None:
    bc = _RecBroadcaster()
    listener = ActionCableListener(session=None, broadcaster=bc)  # type: ignore[arg-type]
    await _stub_token_resolvers(
        listener, user_tokens=["agent_t"], contact_inbox_tokens=["contact_t"]
    )

    contact_inbox = SimpleNamespace(pubsub_token="contact_t", hmac_verified=False)
    conv = SimpleNamespace(
        account_id=1, inbox_id=2, contact_inbox=contact_inbox
    )
    msg = SimpleNamespace(
        # Minimal subset for present_message_push_event — patched below.
        conversation=conv,
        account_id=1,
        private=True,
        message_type=MESSAGE_TYPE_OUTGOING,
    )

    # We don't actually want the presenter to run (it'd choke on the
    # SimpleNamespace). Patch out the data builder.
    import app.domains.conversations.listeners as listeners_mod

    listeners_mod.present_message_push_event = lambda m: {"id": 7}  # type: ignore[assignment]
    try:
        await listener.dispatch(ev.MESSAGE_CREATED, message=msg)
    finally:
        # Restore the real presenter so subsequent tests see it.
        from app.domains.conversations.presenters import (
            present_message_push_event as real_presenter,
        )
        listeners_mod.present_message_push_event = real_presenter  # type: ignore[assignment]

    assert len(bc.calls) == 1
    channels, _event, _payload = bc.calls[0]
    assert channels == ["agent_t"]  # contact dropped due to private


async def test_message_created_excludes_contact_for_activity_message() -> None:
    bc = _RecBroadcaster()
    listener = ActionCableListener(session=None, broadcaster=bc)  # type: ignore[arg-type]
    await _stub_token_resolvers(
        listener, user_tokens=["agent_t"], contact_inbox_tokens=["contact_t"]
    )

    contact_inbox = SimpleNamespace(pubsub_token="contact_t", hmac_verified=False)
    conv = SimpleNamespace(account_id=1, inbox_id=2, contact_inbox=contact_inbox)
    msg = SimpleNamespace(
        conversation=conv,
        account_id=1,
        private=False,
        message_type=MESSAGE_TYPE_ACTIVITY,
    )

    import app.domains.conversations.listeners as listeners_mod

    listeners_mod.present_message_push_event = lambda m: {"id": 8}  # type: ignore[assignment]
    try:
        await listener.dispatch(ev.MESSAGE_CREATED, message=msg)
    finally:
        from app.domains.conversations.presenters import (
            present_message_push_event as real_presenter,
        )
        listeners_mod.present_message_push_event = real_presenter  # type: ignore[assignment]

    assert len(bc.calls) == 1
    channels, _event, _payload = bc.calls[0]
    assert channels == ["agent_t"]


async def test_message_created_includes_contact_for_normal_message() -> None:
    bc = _RecBroadcaster()
    listener = ActionCableListener(session=None, broadcaster=bc)  # type: ignore[arg-type]
    await _stub_token_resolvers(
        listener, user_tokens=["agent_t"], contact_inbox_tokens=["contact_t"]
    )

    contact_inbox = SimpleNamespace(pubsub_token="contact_t", hmac_verified=False)
    conv = SimpleNamespace(account_id=1, inbox_id=2, contact_inbox=contact_inbox)
    msg = SimpleNamespace(
        conversation=conv,
        account_id=1,
        private=False,
        message_type=MESSAGE_TYPE_INCOMING,
    )

    import app.domains.conversations.listeners as listeners_mod

    listeners_mod.present_message_push_event = lambda m: {"id": 9}  # type: ignore[assignment]
    try:
        await listener.dispatch(ev.MESSAGE_CREATED, message=msg)
    finally:
        from app.domains.conversations.presenters import (
            present_message_push_event as real_presenter,
        )
        listeners_mod.present_message_push_event = real_presenter  # type: ignore[assignment]

    assert len(bc.calls) == 1
    channels, _event, _payload = bc.calls[0]
    assert sorted(channels) == ["agent_t", "contact_t"]
