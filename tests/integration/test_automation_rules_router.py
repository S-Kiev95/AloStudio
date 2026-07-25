"""Integration tests for AutomationRule CRUD + condition evaluator.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/automation_rules_controller.rb
  reference/chatwoot/app/policies/automation_rule_policy.rb
  reference/chatwoot/app/models/automation_rule.rb
  reference/chatwoot/app/services/automation_rules/conditions_filter_service.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.automation.conditions import evaluate_conditions
from app.domains.automation.models import AutomationRule
from app.domains.automation.service import run_rule_on_conversation
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONVERSATION_PRIORITY_URGENT,
    CONVERSATION_STATUS_RESOLVED,
    Conversation,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
    update_labels,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_AGENT,
    AccountUser,
)
from app.main import app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _seed_admin(db_session, suffix: str = ""):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@auto.example.com",
            account_name=f"Auto{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _seed_agent_member(db_session, owner_account, suffix: str):
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@auto.example.com",
            account_name=f"Other{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner_account.id,
            user_id=agent.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=agent.user.tokens, uid=agent.user.uid
    )
    agent.user.tokens = new_tokens
    db_session.add(agent.user)
    await db_session.flush()
    return agent, headers.as_response_headers()


async def _seed_conversation(
    db_session, owner, *, contact_email: str | None = None
) -> Conversation:
    inbox = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    contact = Contact(
        account_id=owner.account.id,
        name="X",
        email=contact_email,
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox.inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    return await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------
async def test_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/automation_rules")
    assert resp.status_code == 401


async def test_index_blocked_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, suffix="-ag")
    _agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, suffix="-ag"
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        headers=agent_headers,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CRUD happy paths
# ---------------------------------------------------------------------------
async def test_create_returns_bare_object_no_envelope(client, db_session):
    """Chatwoot's ``create.json.jbuilder`` does NOT wrap in payload."""
    owner, headers = await _seed_admin(db_session, suffix="-cr")
    body = {
        "name": "Auto-resolve VIP",
        "description": "When status hits open AND label vip, resolve.",
        "event_name": "conversation_updated",
        "conditions": [
            {
                "attribute_key": "labels",
                "filter_operator": "equal_to",
                "values": ["vip"],
                "query_operator": "AND",
            },
            {
                "attribute_key": "status",
                "filter_operator": "equal_to",
                "values": ["open"],
                "query_operator": "",
            },
        ],
        "actions": [
            {"action_name": "resolve_conversation", "action_params": []},
        ],
    }
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # No envelope on create.
    assert "payload" not in data
    assert data["name"] == "Auto-resolve VIP"
    assert data["event_name"] == "conversation_updated"
    assert data["active"] is True
    assert isinstance(data["created_on"], int)
    assert data["actions"] == [
        {"action_name": "resolve_conversation", "action_params": []}
    ]


async def test_show_wraps_in_payload(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-sh")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "noop",
            "event_name": "conversation_created",
            "conditions": [],
            "actions": [],
        },
        headers=headers,
    )
    rid = create.json()["id"]
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/automation_rules/{rid}",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "payload" in body
    assert body["payload"]["id"] == rid


async def test_update_changes_active_flag(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-up")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "to-disable",
            "event_name": "conversation_created",
            "conditions": [],
            "actions": [],
        },
        headers=headers,
    )
    rid = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/automation_rules/{rid}",
        json={"active": False},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["payload"]["active"] is False


async def test_destroy_returns_200_empty(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-dl")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "trash",
            "event_name": "conversation_created",
            "conditions": [],
            "actions": [],
        },
        headers=headers,
    )
    rid = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/automation_rules/{rid}",
        headers=headers,
    )
    assert resp.status_code == 200


async def test_clone_creates_new_rule(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-cl")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "Original",
            "event_name": "conversation_updated",
            "conditions": [
                {
                    "attribute_key": "status",
                    "filter_operator": "equal_to",
                    "values": ["open"],
                    "query_operator": "",
                }
            ],
            "actions": [
                {"action_name": "mute_conversation", "action_params": []}
            ],
        },
        headers=headers,
    )
    rid = create.json()["id"]
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules/{rid}/clone",
        headers=headers,
    )
    assert resp.status_code == 200
    cloned = resp.json()["payload"]
    assert cloned["id"] != rid
    assert cloned["name"] == "Original"
    assert cloned["conditions"] == create.json()["conditions"]
    assert cloned["actions"] == create.json()["actions"]


# ---------------------------------------------------------------------------
# Validation 422 paths
# ---------------------------------------------------------------------------
async def test_create_rejects_unknown_event(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-ev")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "bad",
            "event_name": "frobnicated",
            "conditions": [],
            "actions": [],
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_rejects_unknown_condition_attribute(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-bk")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "bad",
            "event_name": "conversation_updated",
            "conditions": [
                {
                    "attribute_key": "unknown_field",
                    "filter_operator": "equal_to",
                    "values": ["x"],
                    "query_operator": "",
                }
            ],
            "actions": [],
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert "not supported" in resp.json()["message"]


async def test_create_rejects_invalid_filter_operator(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-fo")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "bad",
            "event_name": "conversation_updated",
            "conditions": [
                {
                    "attribute_key": "status",
                    "filter_operator": "REGEX_MATCH",
                    "values": ["open"],
                    "query_operator": "",
                }
            ],
            "actions": [],
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_rejects_invalid_query_operator(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-qo")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "bad",
            "event_name": "conversation_updated",
            "conditions": [
                {
                    "attribute_key": "status",
                    "filter_operator": "equal_to",
                    "values": ["open"],
                    "query_operator": "XOR",
                }
            ],
            "actions": [],
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_rejects_unknown_action(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-aa")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "bad",
            "event_name": "conversation_updated",
            "conditions": [],
            "actions": [
                {"action_name": "frobnicate", "action_params": []},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert "frobnicate" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Condition evaluator (unit-style)
# ---------------------------------------------------------------------------
async def test_evaluator_empty_conditions_is_truthy(db_session):
    owner, _ = await _seed_admin(db_session, suffix="-ev0")
    conv = await _seed_conversation(db_session, owner)
    assert evaluate_conditions([], conversation=conv) is True
    assert evaluate_conditions(None, conversation=conv) is True


async def test_evaluator_status_equal_to(db_session):
    owner, _ = await _seed_admin(db_session, suffix="-eqs")
    conv = await _seed_conversation(db_session, owner)
    # Conversation defaults to status=open.
    assert evaluate_conditions(
        [
            {
                "attribute_key": "status",
                "filter_operator": "equal_to",
                "values": ["open"],
                "query_operator": "",
            }
        ],
        conversation=conv,
    )
    assert not evaluate_conditions(
        [
            {
                "attribute_key": "status",
                "filter_operator": "equal_to",
                "values": ["resolved"],
                "query_operator": "",
            }
        ],
        conversation=conv,
    )


async def test_evaluator_labels_equal_to_matches_csv(db_session):
    owner, _ = await _seed_admin(db_session, suffix="-lbl")
    conv = await _seed_conversation(db_session, owner)
    await update_labels(db_session, conversation=conv, titles=["urgent", "vip"])
    assert evaluate_conditions(
        [
            {
                "attribute_key": "labels",
                "filter_operator": "equal_to",
                "values": ["vip"],
                "query_operator": "",
            }
        ],
        conversation=conv,
    )
    assert not evaluate_conditions(
        [
            {
                "attribute_key": "labels",
                "filter_operator": "equal_to",
                "values": ["nope"],
                "query_operator": "",
            }
        ],
        conversation=conv,
    )


async def test_evaluator_contact_email_contains(db_session):
    owner, _ = await _seed_admin(db_session, suffix="-co")
    conv = await _seed_conversation(
        db_session, owner, contact_email="vip@enterprise.example.com"
    )
    contact = await db_session.get(Contact, conv.contact_id)
    assert evaluate_conditions(
        [
            {
                "attribute_key": "email",
                "filter_operator": "contains",
                "values": ["enterprise"],
                "query_operator": "",
            }
        ],
        conversation=conv,
        contact=contact,
    )


async def test_evaluator_combine_and_or(db_session):
    """``[A AND B OR C]`` evaluated left-to-right == ``(A AND B) OR C``."""
    owner, _ = await _seed_admin(db_session, suffix="-cmb")
    conv = await _seed_conversation(db_session, owner)
    await update_labels(db_session, conversation=conv, titles=["sla"])
    # status=open AND label=other (false) OR label=sla (true) ⇒ True
    assert evaluate_conditions(
        [
            {
                "attribute_key": "status",
                "filter_operator": "equal_to",
                "values": ["open"],
                "query_operator": "AND",
            },
            {
                "attribute_key": "labels",
                "filter_operator": "equal_to",
                "values": ["other"],
                "query_operator": "OR",
            },
            {
                "attribute_key": "labels",
                "filter_operator": "equal_to",
                "values": ["sla"],
                "query_operator": "",
            },
        ],
        conversation=conv,
    )


async def test_evaluator_is_present_and_not_present(db_session):
    owner, _ = await _seed_admin(db_session, suffix="-pr")
    conv = await _seed_conversation(db_session, owner)
    # No assignee yet.
    assert not evaluate_conditions(
        [
            {
                "attribute_key": "assignee_id",
                "filter_operator": "is_present",
                "values": [],
                "query_operator": "",
            }
        ],
        conversation=conv,
    )
    assert evaluate_conditions(
        [
            {
                "attribute_key": "assignee_id",
                "filter_operator": "is_not_present",
                "values": [],
                "query_operator": "",
            }
        ],
        conversation=conv,
    )


# ---------------------------------------------------------------------------
# Run-on-conversation
# ---------------------------------------------------------------------------
async def test_run_rule_executes_actions_when_match(client, db_session):
    """End-to-end: rule with `status==open` matches the new conversation,
    then the action runs and flips priority."""
    owner, headers = await _seed_admin(db_session, suffix="-run")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "Tag VIP and resolve",
            "event_name": "conversation_updated",
            "conditions": [
                {
                    "attribute_key": "status",
                    "filter_operator": "equal_to",
                    "values": ["open"],
                    "query_operator": "",
                }
            ],
            "actions": [
                {
                    "action_name": "change_priority",
                    "action_params": ["urgent"],
                },
                {
                    "action_name": "resolve_conversation",
                    "action_params": [],
                },
            ],
        },
        headers=headers,
    )
    assert create.status_code == 200
    rid = create.json()["id"]
    rule = await db_session.get(AutomationRule, rid)
    assert rule is not None

    conv = await _seed_conversation(db_session, owner)
    fired = await run_rule_on_conversation(
        db_session, rule=rule, conversation=conv
    )
    assert fired is True

    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert fresh.priority == CONVERSATION_PRIORITY_URGENT
    assert fresh.status == CONVERSATION_STATUS_RESOLVED


async def test_run_rule_skips_when_inactive(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-ina")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "Inactive",
            "event_name": "conversation_updated",
            "active": False,
            "conditions": [],
            "actions": [
                {
                    "action_name": "resolve_conversation",
                    "action_params": [],
                }
            ],
        },
        headers=headers,
    )
    rid = create.json()["id"]
    rule = await db_session.get(AutomationRule, rid)
    assert rule is not None
    assert rule.active is False
    conv = await _seed_conversation(db_session, owner)
    fired = await run_rule_on_conversation(
        db_session, rule=rule, conversation=conv
    )
    assert fired is False


async def test_run_rule_skips_when_conditions_dont_match(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-skp")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/automation_rules",
        json={
            "name": "OnlyResolved",
            "event_name": "conversation_updated",
            "conditions": [
                {
                    "attribute_key": "status",
                    "filter_operator": "equal_to",
                    "values": ["resolved"],
                    "query_operator": "",
                }
            ],
            "actions": [
                {"action_name": "mute_conversation", "action_params": []}
            ],
        },
        headers=headers,
    )
    rid = create.json()["id"]
    rule = await db_session.get(AutomationRule, rid)
    assert rule is not None
    conv = await _seed_conversation(db_session, owner)  # status=open
    fired = await run_rule_on_conversation(
        db_session, rule=rule, conversation=conv
    )
    assert fired is False
