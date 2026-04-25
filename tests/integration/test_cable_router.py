"""Integration test for the ``/cable`` WebSocket endpoint.

Covers the welcome -> subscribe -> Redis-broadcast -> WS-forward
pipeline against a real Redis. Identifier-parsing, channel selection
and envelope decoding are unit-covered in ``tests/unit/test_cable.py``;
auth resolution (``_resolve_subscriber``) is monkey-patched here so
the test does not depend on user/contact rows — that path is exercised
by parity tests in 4b.6.

Why ``starlette.testclient.TestClient``:
  ``httpx.AsyncClient`` does not speak the ASGI WebSocket sub-protocol,
  so we use Starlette's sync TestClient (which does) inside a sync test
  function. ``pytest-asyncio`` happily co-exists with sync tests.
"""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
import redis as redis_sync
from starlette.testclient import TestClient

from app.core.config import get_settings

pytestmark = pytest.mark.integration


def _read_until(
    ws: Any, predicate: Any, timeout: float = 5.0
) -> dict[str, Any]:
    """Drain frames until ``predicate(frame)`` returns truthy.

    The endpoint emits a ``{type: ping}`` every 3s — those would be the
    only noise frames between subscribe and broadcast forward. We skip
    anything the caller is not waiting for.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = ws.receive_text()
        frame = json.loads(text)
        if predicate(frame):
            return frame
    raise AssertionError("did not receive expected frame within timeout")


def test_cable_pipeline_forwards_redis_publish_to_subscriber(monkeypatch) -> None:
    """End-to-end: connect -> welcome -> subscribe -> publish -> forward.

    Mirrors ``RoomChannel#subscribed`` + the Rails ActionCable forward
    path. We publish raw bytes via a sync redis client (matching the
    on-the-wire format produced by ``RealtimeBroadcaster.encode_envelope``)
    and assert the WS receives a ``{identifier, message}`` frame with
    the decoded envelope.
    """
    import app.core.cable as cable_mod
    from app.main import create_app

    # Bypass DB-backed auth — all the user/contact branches have unit
    # coverage; what we want here is the wire pipeline.
    async def _ok(_pubsub_token, _user_id, _account_id):
        return True

    monkeypatch.setattr(cable_mod, "_resolve_subscriber", _ok)

    settings = get_settings()
    app = create_app()

    identifier = json.dumps(
        {
            "channel": "RoomChannel",
            "pubsub_token": "cable_it_token",
            "user_id": 1,
            "account_id": 1,
        }
    )

    with TestClient(app) as client:
        with client.websocket_connect("/cable") as ws:
            # 1. welcome
            welcome = ws.receive_json()
            assert welcome == {"type": "welcome"}

            # 2. subscribe
            ws.send_text(
                json.dumps({"command": "subscribe", "identifier": identifier})
            )

            confirm = _read_until(
                ws, lambda f: f.get("type") == "confirm_subscription"
            )
            assert confirm == {
                "type": "confirm_subscription",
                "identifier": identifier,
            }

            # 3. Publish to the pubsub_token channel via a sync client.
            #    The pump's ``await self._pubsub.subscribe(...)`` has
            #    already returned by the time confirm arrived, so the
            #    publish is guaranteed to fan out to us.
            r = redis_sync.from_url(settings.redis_url)
            try:
                envelope = json.dumps(
                    {"event": "test.event", "data": {"id": 7}}
                ).encode("utf-8")
                delivered = r.publish("cable_it_token", envelope)
                assert delivered >= 1
            finally:
                r.close()

            # 4. Forward — skip pings, then assert the broadcast shape.
            forward = _read_until(
                ws,
                lambda f: f.get("identifier") == identifier
                and "message" in f
                and "type" not in f,
            )
            assert forward["message"] == {
                "event": "test.event",
                "data": {"id": 7},
            }


def test_cable_two_subscribers_both_receive_broadcast(monkeypatch) -> None:
    """Two clients on the same channel both receive the event.

    Mirrors the PLAN.phase4b.md acceptance criterion: "two clients
    subscribed to the same channel both receive an event fired from a
    third HTTP call". Here the third actor is a sync redis publish —
    semantically identical to the production path where any service
    layer would call ``RealtimeBroadcaster.publish``.
    """
    import app.core.cable as cable_mod
    from app.main import create_app

    async def _ok(_pubsub_token, _user_id, _account_id):
        return True

    monkeypatch.setattr(cable_mod, "_resolve_subscriber", _ok)

    settings = get_settings()
    app = create_app()
    identifier = json.dumps(
        {
            "channel": "RoomChannel",
            "pubsub_token": "cable_it_dual",
            "user_id": 1,
            "account_id": 1,
        }
    )

    with TestClient(app) as client:
        with client.websocket_connect("/cable") as ws_a, client.websocket_connect(
            "/cable"
        ) as ws_b:
            assert ws_a.receive_json() == {"type": "welcome"}
            assert ws_b.receive_json() == {"type": "welcome"}

            for ws in (ws_a, ws_b):
                ws.send_text(
                    json.dumps(
                        {"command": "subscribe", "identifier": identifier}
                    )
                )
                _read_until(
                    ws, lambda f: f.get("type") == "confirm_subscription"
                )

            r = redis_sync.from_url(settings.redis_url)
            try:
                envelope = json.dumps(
                    {"event": "fanout.event", "data": {"id": 99}}
                ).encode("utf-8")
                delivered = r.publish("cable_it_dual", envelope)
                # Both pubsub clients counted — server-side fan-out.
                assert delivered >= 2
            finally:
                r.close()

            for ws in (ws_a, ws_b):
                forward = _read_until(
                    ws,
                    lambda f: f.get("identifier") == identifier
                    and "message" in f
                    and "type" not in f,
                )
                assert forward["message"] == {
                    "event": "fanout.event",
                    "data": {"id": 99},
                }
