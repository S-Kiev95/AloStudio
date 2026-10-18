"""Unit tests for the Meta Business Agent handoff helpers (no DB).

Covers the pure parts of :mod:`app.domains.whatsapp.business_agent`:
reading a ``messaging_handovers`` change (Messenger-shaped keys plus the
WhatsApp variants the parser tolerates), the Thread Control request sent
to Meta (mocked with respx), and the owner stamp on new conversations.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
import respx

import app.main  # noqa: F401  (register SQLModel mappers)
from app.domains.conversations.models import Conversation
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD, WhatsappChannel
from app.domains.whatsapp import business_agent as ba

_URL = "https://api.facebook.com/business/whatsapp/phone_numbers/PID/thread_control"


@pytest.fixture(autouse=True)
def _our_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ba, "get_settings", lambda: SimpleNamespace(meta_app_id="111")
    )


def _channel(**cfg: object) -> WhatsappChannel:
    return WhatsappChannel(
        id=1,
        account_id=1,
        phone_number="+59847325025",
        provider=WHATSAPP_PROVIDER_CLOUD,
        provider_config={"api_key": "tok", "phone_number_id": "PID", **cfg},
    )


# ---------------------------------------------------------------------------
# Handover parsing
# ---------------------------------------------------------------------------
def test_pass_to_our_app_makes_the_team_owner():
    owner, metadata = ba._new_owner(
        {
            "from": "59899123456",
            "pass_thread_control": {
                "previous_owner_app_id": "222",
                "new_owner_app_id": "111",
                "metadata": "Quiere hablar con una persona",
            },
        }
    )
    assert owner == ba.OWNER_APP
    assert metadata == "Quiere hablar con una persona"


def test_pass_to_another_app_leaves_it_with_the_ai():
    owner, _ = ba._new_owner(
        {"pass_thread_control": {"new_owner_app_id": "222"}}
    )
    assert owner == ba.OWNER_AI_AGENT


def test_target_role_ai_agent_and_release_go_back_to_the_ai():
    assert ba._new_owner(
        {"action": "pass", "control_pass": {"target_role": "ai_agent"}}
    )[0] == ba.OWNER_AI_AGENT
    assert ba._new_owner({"release_thread_control": {}})[0] == ba.OWNER_AI_AGENT


def test_pass_without_target_reaches_us_as_the_escalation_partner():
    assert ba._new_owner({"action": "pass"})[0] == ba.OWNER_APP


def test_take_by_the_other_side_means_we_lost_it():
    assert ba._new_owner({"take_thread_control": {}})[0] == ba.OWNER_AI_AGENT


def test_without_meta_app_id_the_action_decides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ba, "get_settings", lambda: SimpleNamespace(meta_app_id=""))
    assert (
        ba._new_owner({"pass_thread_control": {"new_owner_app_id": "111"}})[0]
        == ba.OWNER_APP
    )
    assert (
        ba._new_owner({"take_thread_control": {"new_owner_app_id": "222"}})[0]
        == ba.OWNER_AI_AGENT
    )


def test_unknown_shape_has_no_owner():
    assert ba._new_owner({"something": "else"})[0] is None


def test_consumer_phone_variants():
    own: set[str] = set()
    assert ba._consumer_phone({"from": "598991"}, {}, own=own) == "598991"
    assert ba._consumer_phone({"sender": {"id": "598992"}}, {}, own=own) == "598992"
    assert (
        ba._consumer_phone({}, {"contacts": [{"wa_id": "598993"}]}, own=own)
        == "598993"
    )
    assert ba._consumer_phone({}, {}, own=own) is None


def test_consumer_phone_skips_the_business_own_number():
    own = {"59847325025", "PID"}
    item = {"to": "+59847325025", "from": "59899123456"}
    assert ba._consumer_phone(item, {}, own=own) == "59899123456"
    assert ba._consumer_phone({"recipient": {"id": "PID"}}, {}, own=own) is None


def test_handover_items_accepts_a_list_or_a_single_object():
    assert len(ba._handover_items({"messaging_handovers": [{"a": 1}, {"b": 2}]})) == 2
    assert ba._handover_items({"thread_control": {"a": 1}}) == [{"a": 1}]
    assert ba._handover_items({"from": "1"}) == [{"from": "1"}]


def test_masked_hides_phone_numbers():
    text = ba._masked({"from": "59899123456", "note": "ok"})
    assert "59899123456" not in text
    assert "598***" in text
    assert "ok" in text


# ---------------------------------------------------------------------------
# Owner stamp
# ---------------------------------------------------------------------------
def test_new_conversation_on_a_business_agent_number_starts_with_the_ai():
    conv = Conversation(account_id=1, inbox_id=1, additional_attributes={})
    assert ba.mark_ai_owner_if_unknown(conv, _channel(meta_business_agent=True))
    assert ba.thread_owner(conv) == ba.OWNER_AI_AGENT


def test_owner_stamp_is_skipped_without_the_flag_or_when_known():
    conv = Conversation(account_id=1, inbox_id=1, additional_attributes={})
    assert not ba.mark_ai_owner_if_unknown(conv, _channel())
    assert ba.thread_owner(conv) is None

    owned = Conversation(
        account_id=1,
        inbox_id=1,
        additional_attributes={"thread_control": {"owner": "app"}},
    )
    assert not ba.mark_ai_owner_if_unknown(owned, _channel(meta_business_agent=True))
    assert ba.thread_owner(owned) == ba.OWNER_APP


# ---------------------------------------------------------------------------
# Thread Control request
# ---------------------------------------------------------------------------
@respx.mock
async def test_thread_control_request_shape():
    route = respx.post(_URL).mock(
        return_value=httpx.Response(200, json={"messaging_product": "whatsapp"})
    )
    error = await ba.request_thread_control(
        _channel(), to_phone="+59899123456", action="take", metadata="ref"
    )
    assert error is None
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer tok"
    assert request.headers["X-API-Version"] == "1.0.0"
    assert json.loads(request.content) == {
        "messaging_product": "whatsapp",
        "action": "take",
        "to": "59899123456",
        "metadata": "ref",
    }


@respx.mock
async def test_thread_control_returns_metas_reason_on_error():
    respx.post(_URL).mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "Not the escalation partner"}}
        )
    )
    error = await ba.request_thread_control(
        _channel(), to_phone="59899", action="take"
    )
    assert error == "Not the escalation partner"


async def test_thread_control_needs_credentials():
    channel = _channel()
    channel.provider_config = {}
    error = await ba.request_thread_control(
        channel, to_phone="59899", action="release"
    )
    assert error is not None
