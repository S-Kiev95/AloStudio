"""ActionCable-compatible ``/cable`` WebSocket endpoint.

Implements the subset of Rails' ActionCable protocol that Chatwoot's
frontend dashboard + widget speak. Both consume:

  Server -> Client frames:
    {"type":"welcome"}                                     on connect
    {"type":"ping","message":<unix_seconds>}              every 3s
    {"type":"confirm_subscription","identifier":"<json>"}  on accepted subscribe
    {"type":"reject_subscription","identifier":"<json>"}   on auth miss
    {"identifier":"<json>","message":{"event":"...","data":{...}}}
        on Redis pub/sub forward (note: NO ``type`` key — that's how
        the JS client distinguishes broadcasts from control frames).

  Client -> Server frames:
    {"command":"subscribe","identifier":"<json>"}
    {"command":"unsubscribe","identifier":"<json>"}
    {"command":"message","identifier":"<json>","data":"<json>"}
        — ignored. We don't host any client-callable channel methods
        in 4b.2; presence heartbeat (``RoomChannel#update_presence``)
        lands with 4b.7 / OnlineStatusTracker.

Identifier is itself a JSON-encoded STRING (Rails serializes it that
way) of the shape:

  {"channel":"RoomChannel","pubsub_token":"...","user_id":<int|null>,"account_id":<int|null>}

Auth — mirrors ``RoomChannel#current_user`` + ``current_account``:
  * ``user_id`` present  ->  ``User.find_by!(pubsub_token, id)`` AND
                             the user must be a member of ``account_id``.
  * ``user_id`` absent   ->  ``ContactInbox.find_by!(pubsub_token)``.
  Anything else -> ``reject_subscription``.

Streams (mirrors ``ensure_stream``):
  * ``<pubsub_token>``     (always)
  * ``account_<account_id>`` (Users only)

Ping cadence: 3s — Rails default ``ActionCable::Server::Configuration.
ping_interval``. The ActionCable JS stale-check disconnects after 6s
of frame silence, so anything longer breaks the dashboard.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import select

from app.core.db import get_session_factory
from app.core.realtime import get_broadcaster
from app.domains.contacts.models import ContactInbox
from app.domains.users.models import AccountUser, User

if TYPE_CHECKING:  # pragma: no cover
    from redis.asyncio.client import PubSub

log = logging.getLogger(__name__)

router = APIRouter()

# Match Rails' ``ActionCable::Server::Configuration#ping_interval`` default.
PING_INTERVAL_SECONDS = 3


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.websocket("/cable")
async def cable_endpoint(ws: WebSocket) -> None:
    """ActionCable-compatible WebSocket entry point.

    Mounted at ``/cable`` (the Rails default; Chatwoot's frontend
    config also defaults to this path). Accepts the connection
    immediately and starts a ping loop; per-channel auth happens on
    each ``subscribe`` command.
    """
    await ws.accept()
    await _send(ws, {"type": "welcome"})

    subs: dict[str, _Subscription] = {}
    ping_task = asyncio.create_task(_ping_loop(ws))
    try:
        await _command_loop(ws, subs)
    except WebSocketDisconnect:
        # Normal client close — happens whenever the dashboard tab is
        # backgrounded long enough to trigger the JS reconnect.
        pass
    except Exception:
        log.exception("cable.connection.error")
    finally:
        ping_task.cancel()
        for sub in list(subs.values()):
            await sub.stop()


# ---------------------------------------------------------------------------
# Ping loop
# ---------------------------------------------------------------------------
async def _ping_loop(ws: WebSocket) -> None:
    """Send a ``{type:"ping"}`` frame every ``PING_INTERVAL_SECONDS``.

    Cancellation lands here when the client disconnects or the
    endpoint's ``finally`` block tears down — both expected paths.
    """
    try:
        while True:
            await asyncio.sleep(PING_INTERVAL_SECONDS)
            await _send(ws, {"type": "ping", "message": int(time.time())})
    except (asyncio.CancelledError, WebSocketDisconnect):
        return
    except Exception:
        log.exception("cable.ping.error")


# ---------------------------------------------------------------------------
# Command loop
# ---------------------------------------------------------------------------
async def _command_loop(
    ws: WebSocket, subs: dict[str, _Subscription]
) -> None:
    """Read frames forever, route subscribe/unsubscribe.

    Returns on client disconnect — the caller's ``except
    WebSocketDisconnect`` catches it.
    """
    while True:
        text = await ws.receive_text()
        try:
            frame = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            # Malformed frame — Rails ignores these silently, we do too.
            continue
        if not isinstance(frame, dict):
            continue
        command = frame.get("command")
        identifier = frame.get("identifier")
        if not isinstance(identifier, str):
            continue
        if command == "subscribe":
            await _handle_subscribe(ws, subs, identifier)
        elif command == "unsubscribe":
            await _handle_unsubscribe(subs, identifier)
        # ``command == "message"`` -> ignored (see module docstring).


# ---------------------------------------------------------------------------
# Subscribe
# ---------------------------------------------------------------------------
async def _handle_subscribe(
    ws: WebSocket,
    subs: dict[str, _Subscription],
    identifier_json: str,
) -> None:
    if identifier_json in subs:
        # Re-subscribe to an active identifier is a no-op for us;
        # ActionCable echoes ``confirm_subscription`` regardless so
        # we match that for client-side state simplicity.
        await _send(
            ws,
            {"type": "confirm_subscription", "identifier": identifier_json},
        )
        return

    ident = _parse_identifier(identifier_json)
    if ident is None or ident.get("channel") != "RoomChannel":
        await _send(
            ws,
            {"type": "reject_subscription", "identifier": identifier_json},
        )
        return

    pubsub_token = ident.get("pubsub_token")
    user_id = ident.get("user_id")
    account_id = ident.get("account_id")

    is_user = await _resolve_subscriber(pubsub_token, user_id, account_id)
    if is_user is None:
        await _send(
            ws,
            {"type": "reject_subscription", "identifier": identifier_json},
        )
        return

    channels = _subscription_channels(
        pubsub_token=pubsub_token,
        account_id=account_id,
        is_user=is_user,
    )
    sub = _Subscription(ws=ws, identifier=identifier_json, channels=channels)
    started = await sub.start()
    if not started:
        await _send(
            ws,
            {"type": "reject_subscription", "identifier": identifier_json},
        )
        return
    subs[identifier_json] = sub
    await _send(
        ws, {"type": "confirm_subscription", "identifier": identifier_json}
    )


def _parse_identifier(raw: str) -> dict[str, Any] | None:
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return decoded if isinstance(decoded, dict) else None


async def _resolve_subscriber(
    pubsub_token: str | None,
    user_id: int | None,
    account_id: int | None,
) -> bool | None:
    """Validate the (pubsub_token, user_id, account_id) tuple.

    Returns:
      * ``True``  — User subscriber, also subscribes to ``account_<id>``.
      * ``False`` — ContactInbox subscriber (widget visitor).
      * ``None``  — invalid; caller emits ``reject_subscription``.
    """
    if not pubsub_token or not isinstance(pubsub_token, str):
        return None
    factory = get_session_factory()
    async with factory() as session:
        if user_id is None:
            row = (
                await session.exec(
                    select(ContactInbox).where(ContactInbox.pubsub_token == pubsub_token)
                )
            ).first()
            return False if row is not None else None

        # User branch — must match (pubsub_token, id) AND if account_id
        # was supplied the user must be a member.
        if not isinstance(user_id, int):
            return None
        user_row = (
            await session.exec(
                select(User).where(
                    User.id == user_id, User.pubsub_token == pubsub_token
                )
            )
        ).first()
        if user_row is None:
            return None
        if account_id is not None:
            if not isinstance(account_id, int):
                return None
            membership = (
                await session.exec(
                    select(AccountUser).where(
                        AccountUser.user_id == user_id,
                        AccountUser.account_id == account_id,
                    )
                )
            ).first()
            if membership is None:
                return None
        return True


def _subscription_channels(
    *,
    pubsub_token: str,
    account_id: int | None,
    is_user: bool,
) -> list[str]:
    chs = [pubsub_token]
    if is_user and account_id is not None:
        chs.append(f"account_{account_id}")
    return chs


# ---------------------------------------------------------------------------
# Unsubscribe
# ---------------------------------------------------------------------------
async def _handle_unsubscribe(
    subs: dict[str, _Subscription], identifier_json: str
) -> None:
    sub = subs.pop(identifier_json, None)
    if sub is not None:
        await sub.stop()


# ---------------------------------------------------------------------------
# Subscription — per-channel-group Redis pump
# ---------------------------------------------------------------------------
class _Subscription:
    """One per ``confirm_subscription``. Owns a Redis pubsub object +
    a forwarding task that reads messages and writes them to the WS.

    Cleanly shut down by ``stop()`` — cancels the task, unsubscribes,
    closes the pubsub object. Defensive ``except`` everywhere because
    a Redis flake must not bubble out of the WS handler.
    """

    def __init__(
        self,
        *,
        ws: WebSocket,
        identifier: str,
        channels: list[str],
    ) -> None:
        self._ws = ws
        self._identifier = identifier
        self._channels = channels
        self._task: asyncio.Task[None] | None = None
        self._pubsub: PubSub | None = None

    async def start(self) -> bool:
        """Subscribe to Redis + start the pump. Returns True on success."""
        try:
            broadcaster = await get_broadcaster()
            self._pubsub = broadcaster.redis.pubsub()
            await self._pubsub.subscribe(*self._channels)
            self._task = asyncio.create_task(self._pump())
            return True
        except Exception:
            log.exception("cable.subscription.start.error")
            await self._close_pubsub()
            return False

    async def _pump(self) -> None:
        assert self._pubsub is not None
        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "message":
                    # Skip control messages (subscribe/unsubscribe acks).
                    continue
                envelope = _decode_envelope(message.get("data"))
                if envelope is None:
                    continue
                await _send(
                    self._ws,
                    {"identifier": self._identifier, "message": envelope},
                )
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("cable.subscription.pump.error")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            # We just cancelled it, so CancelledError is the expected outcome;
            # anything else it raises on the way out is equally moot here.
            with suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None
        await self._close_pubsub()

    async def _close_pubsub(self) -> None:
        if self._pubsub is None:
            return
        # Teardown is best-effort: a dead connection must not mask the reason
        # we're shutting down in the first place.
        with suppress(Exception):
            await self._pubsub.unsubscribe(*self._channels)
        with suppress(Exception):
            await self._pubsub.aclose()
        self._pubsub = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _send(ws: WebSocket, frame: dict[str, Any]) -> None:
    """Wrap ``ws.send_text`` with a try/except.

    A WS write that races with the client closing should not crash the
    enclosing task — we just give up and let the disconnect path tear
    things down.
    """
    try:
        await ws.send_text(json.dumps(frame))
    except (WebSocketDisconnect, RuntimeError):
        return
    except Exception:
        log.exception("cable.send.error")


def _decode_envelope(payload: Any) -> dict[str, Any] | None:
    """Decode the JSON published by :class:`RealtimeBroadcaster`.

    Returns ``None`` for malformed payloads — should not happen in
    practice but we don't want a stray PUBLISH from another writer to
    take down the WS.
    """
    if isinstance(payload, (bytes, str)):
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(decoded, dict):
            return decoded
    return None


__all__ = ["cable_endpoint", "router"]
