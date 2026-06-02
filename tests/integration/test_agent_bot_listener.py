"""End-to-end tests for the AgentBotListener.

Each test seeds a bot + attaches it to an inbox, triggers a
dispatcher event, and asserts the bot's ``outgoing_url`` received the
expected POST.

Anchors:
  reference/chatwoot/app/listeners/agent_bot_listener.rb
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest
import respx

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.agent_bots.models import AgentBot, AgentBotInbox
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import Conversation
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
    toggle_status,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration


async def _seed_account(db_session, suffix: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@blst.example.com",
            account_name=f"BLst{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _seed_bot_attached(
    db_session,
    owner,
    *,
    outgoing_url: str,
    secret: str = "topsecret123",
) -> tuple[AgentBot, Conversation]:
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
    bot = AgentBot(
        account_id=owner.account.id,
        name="Triage",
        outgoing_url=outgoing_url,
        secret=secret,
    )
    db_session.add(bot)
    await db_session.flush()
    await db_session.refresh(bot)
    db_session.add(
        AgentBotInbox(
            account_id=owner.account.id,
            inbox_id=inbox.inbox.id,
            agent_bot_id=bot.id,
            status=0,
        )
    )
    await db_session.flush()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    return bot, conv


# ---------------------------------------------------------------------------
# message_created
# ---------------------------------------------------------------------------
@respx.mock
async def test_message_created_posts_to_outgoing_url(db_session):
    owner = await _seed_account(db_session, "-mc")
    bot, conv = await _seed_bot_attached(
        db_session, owner, outgoing_url="https://bot.example.com/hook"
    )
    route = respx.post("https://bot.example.com/hook").mock(
        return_value=httpx.Response(200)
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="hello bot",
            message_type="incoming",
        ),
        user_id=None,
    )
    assert route.called
    payload = json.loads(route.calls.last.request.content)
    assert payload["event"] == "message_created"
    assert payload["content"] == "hello bot"
    assert payload["message_type"] == "incoming"
    assert payload["conversation"]["id"] == conv.id
    assert payload["conversation"]["account_id"] == owner.account.id
    # v2.7: ``event_id`` mirrors the delivery header so receivers can
    # dedupe straight from the body.
    assert "event_id" in payload
    assert len(payload["event_id"]) == 36
    delivery_header = route.calls.last.request.headers["X-Chatwoot-Delivery"]
    assert delivery_header == payload["event_id"]
    # v2.7: ``sender_type`` is the lowercase STI label. The incoming
    # message above was created without a sender, so the channel layer
    # leaves the field NULL — verify the key still appears (so
    # receivers can branch without a hasattr check).
    assert "sender_type" in payload


@respx.mock
async def test_message_created_skipped_for_activity_messages(db_session):
    """Activity messages (status flips, label changes) are NOT
    webhook-sendable — listener must not POST."""
    owner = await _seed_account(db_session, "-act")
    bot, conv = await _seed_bot_attached(
        db_session, owner, outgoing_url="https://bot.example.com/skip"
    )
    route = respx.post("https://bot.example.com/skip").mock(
        return_value=httpx.Response(200)
    )
    # ``toggle_status`` inserts an activity message as a side-effect.
    await toggle_status(db_session, conversation=conv, status="resolved")
    # The activity message must not have triggered a relay (the
    # conversation_resolved event itself DOES fire — see other test).
    sent_events = [
        json.loads(c.request.content)["event"] for c in route.calls
    ]
    assert "message_created" not in sent_events


@respx.mock
async def test_signature_header_is_hmac_sha256_of_body(db_session):
    owner = await _seed_account(db_session, "-sig")
    bot, conv = await _seed_bot_attached(
        db_session,
        owner,
        outgoing_url="https://bot.example.com/sig",
        secret="my-bot-secret",
    )
    route = respx.post("https://bot.example.com/sig").mock(
        return_value=httpx.Response(200)
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="check sig",
            message_type="incoming",
        ),
        user_id=None,
    )
    req = route.calls.last.request
    expected_sig = hmac.new(
        b"my-bot-secret", req.content, hashlib.sha256
    ).hexdigest()
    assert req.headers["X-Chatwoot-Signature"] == expected_sig
    # v2.7 dual header: modern ``sha256=<hex>`` form, same digest.
    assert req.headers["X-AloStudio-Signature"] == f"sha256={expected_sig}"
    # Delivery ID present + UUID-shaped.
    assert "X-Chatwoot-Delivery" in req.headers
    assert len(req.headers["X-Chatwoot-Delivery"]) == 36


@respx.mock
async def test_no_post_when_bot_has_no_outgoing_url(db_session):
    """Bot with NULL ``outgoing_url`` is configured but inert."""
    owner = await _seed_account(db_session, "-no")
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
        source_id="src-nourl",
    ).perform()
    bot = AgentBot(
        account_id=owner.account.id,
        name="NoUrl",
        outgoing_url=None,
        secret="x",
    )
    db_session.add(bot)
    await db_session.flush()
    await db_session.refresh(bot)
    db_session.add(
        AgentBotInbox(
            account_id=owner.account.id,
            inbox_id=inbox.inbox.id,
            agent_bot_id=bot.id,
            status=0,
        )
    )
    await db_session.flush()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    catch_all = respx.post(host="bot.example.com").mock(
        return_value=httpx.Response(200)
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="x", message_type="incoming"),
        user_id=None,
    )
    assert not catch_all.called


# ---------------------------------------------------------------------------
# Conversation lifecycle events
# ---------------------------------------------------------------------------
@respx.mock
async def test_conversation_resolved_relays_event(db_session):
    owner = await _seed_account(db_session, "-cr")
    bot, conv = await _seed_bot_attached(
        db_session, owner, outgoing_url="https://bot.example.com/conv"
    )
    route = respx.post("https://bot.example.com/conv").mock(
        return_value=httpx.Response(200)
    )
    await toggle_status(db_session, conversation=conv, status="resolved")

    sent = [json.loads(c.request.content) for c in route.calls]
    events = [b["event"] for b in sent]
    # toggle_status fires status_changed + resolved.
    assert "conversation_status_changed" in events
    assert "conversation_resolved" in events
    resolved_body = next(
        b for b in sent if b["event"] == "conversation_resolved"
    )
    assert resolved_body["id"] == conv.id
    assert resolved_body["status"] == "resolved"


@respx.mock
async def test_listener_does_not_post_when_no_bot_attached(db_session):
    """The listener must short-circuit cleanly when an inbox has no
    bot attached — common case."""
    owner = await _seed_account(db_session, "-nob")
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
        source_id="src-nobot",
    ).perform()
    catch_all = respx.post(host="bot.example.com").mock(
        return_value=httpx.Response(200)
    )
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="x", message_type="incoming"),
        user_id=None,
    )
    assert not catch_all.called


@respx.mock
async def test_non_2xx_response_does_not_break_request(db_session):
    """The bot returning 500 must not raise back into the message-create
    flow — failure-isolation contract."""
    owner = await _seed_account(db_session, "-500")
    bot, conv = await _seed_bot_attached(
        db_session, owner, outgoing_url="https://bot.example.com/500"
    )
    respx.post("https://bot.example.com/500").mock(
        return_value=httpx.Response(500, json={"err": "boom"})
    )
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="x", message_type="incoming"),
        user_id=None,
    )
    assert msg.id is not None
