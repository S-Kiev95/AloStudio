"""Parity tests for the Facebook Messenger webhook surface.

Anchors:
  reference/chatwoot/config/routes.rb (mount Facebook::Messenger::Server at: 'bot')
  reference/chatwoot/config/initializers/facebook_messenger.rb

Scope note — Chatwoot mounts the ``facebook-messenger`` Ruby gem
verbatim under ``/bot``. The gem's verify-token + payload-parse
implementation predates strict-mode Meta requirements: it returns
2xx even for unknown verify tokens (the gem just decides not to
echo back), and it 500s on bodies it can't parse. AloStudio
implements the verify-token + accept-anything-200 flow directly so
we get fail-closed verification + retry-loop-friendly 200s.

The parity surface that genuinely matches both backends is small:

  * A correctly-shaped Messenger POST acks 200 on both sides.

Verify-token + malformed-body branches are deliberate divergences
documented in `app/domains/facebook/router.py`.
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


async def test_receive_well_formed_acks_200(alo_client, cw_client):
    """A standard Messenger payload with no matching page on either
    backend gets a 200 ack on both sides — the queue-without-lookup
    convention."""
    body = {
        "object": "page",
        "entry": [
            {
                "id": "999999999999",
                "time": 1700000000,
                "messaging": [],
            }
        ],
    }
    alo = await alo_client.post("/bot", json=body)
    cw = await cw_client.post("/bot", json=body)
    assert alo.status_code == cw.status_code
    assert alo.status_code == 200


# Keep harness import live for body-shape parity additions later.
_ = assert_json_parity
