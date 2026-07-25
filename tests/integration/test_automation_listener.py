"""End-to-end tests for the AutomationRuleListener.

The listener subscribes to dispatcher events fired by the
conversation + message services. Each test seeds a rule, performs an
operation that dispatches the matching event, and asserts the rule's
actions ran.

Anchors:
  reference/chatwoot/app/listeners/automation_rule_listener.rb
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.automation.models import AutomationRule
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONVERSATION_PRIORITY_HIGH,
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
    toggle_priority,
    toggle_status,
    update_labels,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _seed_account(db_session, suffix: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@autolst.example.com",
            account_name=f"AutoLst{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _seed_conversation(db_session, owner) -> Conversation:
    inbox = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    contact = Contact(account_id=owner.account.id, name="X")
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


async def _make_rule(
    db_session,
    *,
    account_id: int,
    event_name: str,
    conditions: list[dict],
    actions: list[dict],
    active: bool = True,
    name: str = "test-rule",
) -> AutomationRule:
    rule = AutomationRule(
        account_id=account_id,
        name=name,
        event_name=event_name,
        active=active,
        conditions=conditions,
        actions=actions,
    )
    db_session.add(rule)
    await db_session.flush()
    await db_session.refresh(rule)
    return rule


# ---------------------------------------------------------------------------
# conversation_created
# ---------------------------------------------------------------------------
async def test_listener_fires_on_conversation_created(db_session):
    """A rule on ``conversation_created`` with empty conditions fires
    for every new conversation."""
    owner = await _seed_account(db_session, suffix="-cc")
    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="conversation_created",
        conditions=[],
        actions=[
            {"action_name": "change_priority", "action_params": ["high"]}
        ],
    )
    conv = await _seed_conversation(db_session, owner)
    # The listener already fired during create_conversation's dispatch.
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert fresh.priority == CONVERSATION_PRIORITY_HIGH


# ---------------------------------------------------------------------------
# conversation_updated  (also covers loop prevention)
# ---------------------------------------------------------------------------
async def test_listener_fires_on_conversation_updated(db_session):
    """``toggle_priority`` dispatches ``CONVERSATION_UPDATED``; the
    rule listens for that and applies a label."""
    owner = await _seed_account(db_session, suffix="-cu")
    conv = await _seed_conversation(db_session, owner)
    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="conversation_updated",
        conditions=[
            {
                "attribute_key": "priority",
                "filter_operator": "equal_to",
                "values": ["urgent"],
                "query_operator": "",
            }
        ],
        actions=[
            {"action_name": "add_label", "action_params": ["sla-breach"]}
        ],
    )
    # Trigger conversation_updated by changing priority.
    await toggle_priority(
        db_session, conversation=conv, priority="urgent"
    )
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert (fresh.cached_label_list or "") == "sla-breach"


async def test_listener_does_not_loop_on_self_triggered_event(db_session):
    """A rule that fires on ``conversation_updated`` and itself
    triggers ``conversation_updated`` (via change_priority) must NOT
    re-trigger. The marker ContextVar short-circuits the second pass."""
    owner = await _seed_account(db_session, suffix="-loop")
    conv = await _seed_conversation(db_session, owner)
    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="conversation_updated",
        # Matches every update.
        conditions=[],
        actions=[
            {"action_name": "change_priority", "action_params": ["high"]}
        ],
    )
    # Fire the first update — should run actions, which themselves
    # dispatch conversation_updated, which the listener must ignore.
    await toggle_priority(
        db_session, conversation=conv, priority="medium"
    )
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    # Action ran (priority overwritten by the rule) and no infinite
    # recursion happened — if it had, we'd time out / blow the stack.
    assert fresh.priority == CONVERSATION_PRIORITY_HIGH


# ---------------------------------------------------------------------------
# conversation_opened / conversation_resolved
# ---------------------------------------------------------------------------
async def test_listener_fires_on_conversation_resolved(db_session):
    owner = await _seed_account(db_session, suffix="-cr")
    conv = await _seed_conversation(db_session, owner)
    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="conversation_resolved",
        conditions=[],
        actions=[
            {"action_name": "add_label", "action_params": ["closed"]}
        ],
    )
    await toggle_status(
        db_session, conversation=conv, status="resolved"
    )
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert fresh.status == CONVERSATION_STATUS_RESOLVED
    assert (fresh.cached_label_list or "") == "closed"


async def test_listener_fires_on_conversation_opened(db_session):
    owner = await _seed_account(db_session, suffix="-co")
    conv = await _seed_conversation(db_session, owner)
    # Move to resolved so we have somewhere to come back from.
    await toggle_status(db_session, conversation=conv, status="resolved")
    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="conversation_opened",
        conditions=[],
        actions=[
            {"action_name": "change_priority", "action_params": ["high"]}
        ],
    )
    await toggle_status(db_session, conversation=conv, status="open")
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert fresh.status == CONVERSATION_STATUS_OPEN
    assert fresh.priority == CONVERSATION_PRIORITY_HIGH


# ---------------------------------------------------------------------------
# message_created  (also covers activity / private filtering)
# ---------------------------------------------------------------------------
async def test_listener_fires_on_message_created(db_session):
    owner = await _seed_account(db_session, suffix="-mc")
    conv = await _seed_conversation(db_session, owner)
    await update_labels(db_session, conversation=conv, titles=[])
    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="message_created",
        conditions=[
            {
                "attribute_key": "content",
                "filter_operator": "contains",
                "values": ["refund"],
                "query_operator": "",
            }
        ],
        actions=[
            {"action_name": "add_label", "action_params": ["refund-request"]}
        ],
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="I want a refund please",
            message_type="incoming",
        ),
        user_id=None,
    )
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert (fresh.cached_label_list or "") == "refund-request"


async def test_listener_ignores_activity_messages(db_session):
    """Activity messages must not fire ``message_created`` rules
    (mirrors ``ignore_message_created_event?``)."""
    owner = await _seed_account(db_session, suffix="-mac")
    conv = await _seed_conversation(db_session, owner)
    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="message_created",
        conditions=[],
        actions=[
            {"action_name": "add_label", "action_params": ["should-not-fire"]}
        ],
    )
    # Trigger an activity message via toggle_status (it inserts one
    # as a side-effect of changing status).
    await toggle_status(db_session, conversation=conv, status="resolved")
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    # If the listener had matched the activity message, the label
    # would've been applied. The toggle_status above DOES dispatch
    # conversation_resolved + conversation_updated, but those don't
    # have ``content`` matching the empty conditions check on
    # message_created — the message body would have been the activity
    # text. We assert the label is absent.
    assert "should-not-fire" not in (fresh.cached_label_list or "")


async def test_listener_skips_inactive_rule(db_session):
    owner = await _seed_account(db_session, suffix="-ina")
    conv = await _seed_conversation(db_session, owner)
    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="conversation_updated",
        conditions=[],
        actions=[
            {"action_name": "add_label", "action_params": ["disabled-rule"]}
        ],
        active=False,
    )
    await toggle_priority(db_session, conversation=conv, priority="urgent")
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert "disabled-rule" not in (fresh.cached_label_list or "")


async def test_listener_isolates_per_account(db_session):
    """A rule on Account A must not fire for a conversation on Account B."""
    owner_a = await _seed_account(db_session, suffix="-ax")
    owner_b = await _seed_account(db_session, suffix="-bx")
    await _make_rule(
        db_session,
        account_id=owner_a.account.id,
        event_name="conversation_created",
        conditions=[],
        actions=[
            {"action_name": "add_label", "action_params": ["a-only"]}
        ],
    )
    conv_b = await _seed_conversation(db_session, owner_b)
    fresh = await db_session.get(Conversation, conv_b.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert "a-only" not in (fresh.cached_label_list or "")


async def test_listener_runs_send_message_action(db_session):
    """``send_message`` action creates an outgoing message on the
    conversation."""
    owner = await _seed_account(db_session, suffix="-sm")
    conv = await _seed_conversation(db_session, owner)
    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="message_created",
        conditions=[
            {
                "attribute_key": "message_type",
                "filter_operator": "equal_to",
                "values": ["incoming"],
                "query_operator": "",
            }
        ],
        actions=[
            {
                "action_name": "send_message",
                "action_params": ["Auto reply: we got your message."],
            }
        ],
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="Hi, I need help",
            message_type="incoming",
        ),
        user_id=None,
    )
    outgoing = list(
        (
            await db_session.exec(
                select(Message).where(
                    Message.conversation_id == conv.id,
                    Message.message_type == MESSAGE_TYPE_OUTGOING,
                )
            )
        ).all()
    )
    assert len(outgoing) == 1
    assert outgoing[0].content == "Auto reply: we got your message."


# ---------------------------------------------------------------------------
# v2.8 — ai_mode suppression
# ---------------------------------------------------------------------------
async def test_listener_skips_when_conversation_in_ai_mode(db_session):
    """A rule that would otherwise fire on ``conversation_updated``
    short-circuits when ``conversation.ai_mode`` is true — the AI
    agent has taken over and our automation must stand down."""
    owner = await _seed_account(db_session, suffix="-aimode")
    conv = await _seed_conversation(db_session, owner)
    # Flip ai_mode on BEFORE the trigger event fires.
    conv.ai_mode = True
    conv.ai_assignee = "alicia-v3"
    db_session.add(conv)
    await db_session.flush()

    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="conversation_updated",
        conditions=[],
        actions=[
            {"action_name": "add_label", "action_params": ["should-not-fire"]}
        ],
    )
    # Trigger CONVERSATION_UPDATED via toggle_priority.
    await toggle_priority(
        db_session, conversation=conv, priority="high"
    )
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    # Priority did flip (toggle_priority itself runs unconditionally),
    # but the rule's label action was suppressed.
    assert fresh.priority == CONVERSATION_PRIORITY_HIGH
    assert (fresh.cached_label_list or "") == ""


async def test_listener_resumes_when_ai_mode_turned_off(db_session):
    """Flipping ``ai_mode`` back to false re-enables the automation
    cascade — the same rule + trigger that was suppressed in the
    previous test now fires normally."""
    owner = await _seed_account(db_session, suffix="-aiback")
    conv = await _seed_conversation(db_session, owner)
    conv.ai_mode = False
    db_session.add(conv)
    await db_session.flush()

    await _make_rule(
        db_session,
        account_id=owner.account.id,
        event_name="conversation_updated",
        conditions=[],
        actions=[
            {"action_name": "add_label", "action_params": ["sla-watch"]}
        ],
    )
    await toggle_priority(
        db_session, conversation=conv, priority="high"
    )
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert (fresh.cached_label_list or "") == "sla-watch"
