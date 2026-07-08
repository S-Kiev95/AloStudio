"""Integration tests for bot-handling tracking + the bot-metrics report.

Two halves:

  * The ReportingEventListener now writes ``conversation_bot_resolved``
    (on resolve, when the inbox has an active bot and no human replied)
    and ``conversation_bot_handoff`` (on ``bot_handoff``, deduped).
  * ``V2::Reports::BotMetricsBuilder`` → :func:`bot_metrics` turns those
    rows + the bot inbox's conversations/messages into the four report
    numbers, surfaced at ``GET /reports/bot_metrics``.

Anchors:
  reference/chatwoot/app/listeners/reporting_event_listener.rb
  reference/chatwoot/app/builders/v2/reports/bot_metrics_builder.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.agent_bots.models import AgentBot, AgentBotInbox
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import Conversation
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    bot_handoff,
    create_conversation,
    create_message,
    toggle_status,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.reporting.bot_metrics import bot_metrics
from app.domains.reporting.models import ReportingEvent
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration


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


async def _seed_account(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@bot.example.com",
            account_name=f"Bot{suffix}",
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


async def _make_inbox(db_session, owner, name: str):
    return (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name=name,
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox


async def _attach_bot(db_session, owner, inbox, *, status: int = 0):
    bot = AgentBot(
        account_id=owner.account.id, name="Triage", outgoing_url="https://b/x"
    )
    db_session.add(bot)
    await db_session.flush()
    await db_session.refresh(bot)
    db_session.add(
        AgentBotInbox(
            account_id=owner.account.id,
            inbox_id=inbox.id,
            agent_bot_id=bot.id,
            status=status,
        )
    )
    await db_session.flush()
    return bot


async def _contact_inbox(db_session, owner, inbox, source_id: str):
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    return await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox, source_id=source_id
    ).perform()


async def _conv(db_session, ci, *, when: datetime | None = None) -> Conversation:
    # create_conversation reads contact_inbox.inbox — load it in async
    # context first (see memory: reference_live_verify_recipe).
    await db_session.refresh(ci, ["inbox"])
    conv = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )
    if when is not None:
        conv.created_at = when
        db_session.add(conv)
        await db_session.flush()
    return conv


async def _events(db_session, conv, name) -> list[ReportingEvent]:
    return list(
        (
            await db_session.exec(
                select(ReportingEvent).where(
                    ReportingEvent.conversation_id == conv.id,
                    ReportingEvent.name == name,
                )
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# conversation_bot_resolved
# ---------------------------------------------------------------------------
async def test_bot_resolve_emits_bot_resolved_event(db_session):
    owner, _ = await _seed_account(db_session, "-br")
    inbox = await _make_inbox(db_session, owner, "Bot API")
    await _attach_bot(db_session, owner, inbox)
    ci = await _contact_inbox(db_session, owner, inbox, "s-br")
    conv = await _conv(db_session, ci)

    await toggle_status(db_session, conversation=conv, status="resolved")

    # Both the base resolved event and the bot-resolved copy exist.
    assert len(await _events(db_session, conv, "conversation_resolved")) == 1
    bot_events = await _events(db_session, conv, "conversation_bot_resolved")
    assert len(bot_events) == 1
    assert bot_events[0].account_id == owner.account.id
    assert bot_events[0].inbox_id == inbox.id


async def test_human_reply_suppresses_bot_resolved(db_session):
    owner, _ = await _seed_account(db_session, "-hr")
    inbox = await _make_inbox(db_session, owner, "Bot API")
    await _attach_bot(db_session, owner, inbox)
    ci = await _contact_inbox(db_session, owner, inbox, "s-hr")
    conv = await _conv(db_session, ci)
    # A human agent replied → not a bot resolution.
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="hi", message_type="outgoing"),
        user_id=owner.user.id,
    )

    await toggle_status(db_session, conversation=conv, status="resolved")

    assert len(await _events(db_session, conv, "conversation_resolved")) == 1
    assert await _events(db_session, conv, "conversation_bot_resolved") == []


async def test_no_bot_inbox_skips_bot_resolved(db_session):
    owner, _ = await _seed_account(db_session, "-nb")
    inbox = await _make_inbox(db_session, owner, "Plain API")  # no bot attached
    ci = await _contact_inbox(db_session, owner, inbox, "s-nb")
    conv = await _conv(db_session, ci)

    await toggle_status(db_session, conversation=conv, status="resolved")

    assert len(await _events(db_session, conv, "conversation_resolved")) == 1
    assert await _events(db_session, conv, "conversation_bot_resolved") == []


async def test_paused_bot_skips_bot_resolved(db_session):
    owner, _ = await _seed_account(db_session, "-pb")
    inbox = await _make_inbox(db_session, owner, "Paused API")
    await _attach_bot(db_session, owner, inbox, status=1)  # paused
    ci = await _contact_inbox(db_session, owner, inbox, "s-pb")
    conv = await _conv(db_session, ci)

    await toggle_status(db_session, conversation=conv, status="resolved")

    assert await _events(db_session, conv, "conversation_bot_resolved") == []


# ---------------------------------------------------------------------------
# conversation_bot_handoff
# ---------------------------------------------------------------------------
async def test_bot_handoff_emits_event_once(db_session):
    owner, _ = await _seed_account(db_session, "-ho")
    inbox = await _make_inbox(db_session, owner, "Bot API")
    await _attach_bot(db_session, owner, inbox)
    ci = await _contact_inbox(db_session, owner, inbox, "s-ho")
    conv = await _conv(db_session, ci)
    conv.created_at = datetime.now(UTC) - timedelta(seconds=30)
    db_session.add(conv)
    await db_session.flush()

    await bot_handoff(db_session, conversation=conv)
    await bot_handoff(db_session, conversation=conv)  # deduped

    events = await _events(db_session, conv, "conversation_bot_handoff")
    assert len(events) == 1
    assert events[0].value >= 30.0


# ---------------------------------------------------------------------------
# The report builder + endpoint
# ---------------------------------------------------------------------------
async def test_bot_metrics_aggregation_and_rates(client, db_session):
    owner, headers = await _seed_account(db_session, "-agg")
    bot_inbox = await _make_inbox(db_session, owner, "Bot API")
    await _attach_bot(db_session, owner, bot_inbox)
    plain_inbox = await _make_inbox(db_session, owner, "Plain API")

    bot_ci = await _contact_inbox(db_session, owner, bot_inbox, "s-agg-b")
    plain_ci = await _contact_inbox(db_session, owner, plain_inbox, "s-agg-p")

    # 3 bot conversations: A resolved-by-bot, B handed off, C with 2 msgs.
    conv_a = await _conv(db_session, bot_ci)
    await toggle_status(db_session, conversation=conv_a, status="resolved")

    conv_b = await _conv(db_session, bot_ci)
    await bot_handoff(db_session, conversation=conv_b)

    conv_c = await _conv(db_session, bot_ci)
    for _ in range(2):
        await create_message(
            db_session,
            conversation=conv_c,
            params=MessageBuilderParams(content="hi", message_type="outgoing"),
            user_id=owner.user.id,
        )

    # A non-bot conversation + message must be excluded entirely.
    conv_d = await _conv(db_session, plain_ci)
    await create_message(
        db_session,
        conversation=conv_d,
        params=MessageBuilderParams(content="hi", message_type="outgoing"),
        user_id=owner.user.id,
    )

    since = datetime.now(UTC) - timedelta(hours=1)
    until = datetime.now(UTC) + timedelta(hours=1)
    metrics = await bot_metrics(
        db_session, account_id=owner.account.id, since=since, until=until
    )
    assert metrics == {
        "conversation_count": 3,
        "message_count": 2,
        "resolution_rate": 33,  # int(1 / 3 * 100)
        "handoff_rate": 33,
    }

    # Endpoint wire shape (agent-or-admin auth; here the owner is admin).
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/bot_metrics"
        f"?since={int(since.timestamp())}&until={int(until.timestamp())}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == metrics


async def test_bot_metrics_empty_is_all_zeroes(client, db_session):
    owner, headers = await _seed_account(db_session, "-zero")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/bot_metrics",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "conversation_count": 0,
        "message_count": 0,
        "resolution_rate": 0,
        "handoff_rate": 0,
    }
