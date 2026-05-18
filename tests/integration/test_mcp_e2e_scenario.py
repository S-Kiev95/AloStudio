"""End-to-end MCP scenario test — covers the full agent loop.

Walks through what a real AI agent would do in production:
  1. Connect via Bearer token.
  2. ``whoami`` to confirm scope.
  3. ``list_conversations`` to discover work.
  4. ``show_conversation`` to read context.
  5. ``send_message`` to reply.
  6. ``add_label`` to tag the topic.
  7. ``set_conversation_custom_attribute`` to stash agent state.
  8. ``resolve_conversation`` when done.

Every step exercises the full FastMCP middleware + tool dispatch
+ service layer + event cascade. This is the test that catches any
regression between the MCP layer and the underlying domains.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from fastmcp import Client
from sqlalchemy import NullPool, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.accounts.models import Account
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONVERSATION_STATUS_RESOLVED,
    Conversation,
    Message,
    MESSAGE_TYPE_OUTGOING,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.reporting.models import ReportingEvent
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.mcp.server import build_server
from app.mcp.service import create_token

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _clear_token_env():
    prev = os.environ.pop("MCP_BEARER_TOKEN", None)
    yield
    if prev is None:
        os.environ.pop("MCP_BEARER_TOKEN", None)
    else:
        os.environ["MCP_BEARER_TOKEN"] = prev


@pytest.fixture
async def mcp_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        get_settings().database_url, poolclass=NullPool
    )
    created: list[int] = []
    try:
        sm = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with sm() as session:
            session._mcp_accts = created  # type: ignore[attr-defined]
            yield session
        async with sm() as cleanup:
            if created:
                await cleanup.exec(  # type: ignore[call-overload]
                    delete(Account).where(Account.id.in_(created))  # type: ignore[union-attr]
                )
                await cleanup.commit()
    finally:
        await engine.dispose()


def _body(result):
    return result.structured_content or result.data


async def test_full_agent_loop_against_real_conversation(mcp_session):
    """A complete agent run — from authentication to resolution —
    against a freshly-seeded conversation."""
    import secrets

    uniq = secrets.token_hex(4)
    # ---- seed: account + token + inbox + contact + conv + 1 message
    owner = await AccountBuilder(
        mcp_session,
        AccountBuilderParams(
            email=f"admin-{uniq}@e2e.mcp.example.com",
            account_name=f"E2E-MCP-{uniq}",
            user_full_name="E2E Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            mcp_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox
    contact = Contact(account_id=owner.account.id, name="Diana")
    mcp_session.add(contact)
    await mcp_session.flush()
    ci = await ContactInboxBuilder(
        session=mcp_session,
        contact=contact,
        inbox=inbox,
        source_id=f"e2e-{contact.id}",
    ).perform()
    conv = await create_conversation(
        mcp_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    await create_message(
        mcp_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="My order #4242 hasn't shipped, can you help?",
            message_type="incoming",
        ),
        user_id=None,
    )
    token = await create_token(
        mcp_session,
        account_id=owner.account.id,
        name="auto-reply-agent",
        scope="write",
        user_id=owner.user.id,
    )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token.token

    # ---- agent loop
    mcp = build_server()
    async with Client(mcp) as client:
        # 1. whoami
        identity = _body(await client.call_tool("whoami", {}))
        assert identity["account_id"] == owner.account.id
        assert identity["scope"] == "write"

        # 2. discover open conversations
        listing = _body(await client.call_tool("list_conversations", {}))
        assert len(listing["conversations"]) == 1
        target_id = listing["conversations"][0]["id"]
        assert target_id == conv.id

        # 3. read context
        full = _body(
            await client.call_tool(
                "show_conversation", {"conversation_id": target_id}
            )
        )
        assert "order #4242" in full["messages"][0]["content"]

        # 4. detect intent + stash on custom_attribute
        _body(
            await client.call_tool(
                "set_conversation_custom_attribute",
                {
                    "conversation_id": target_id,
                    "key": "intent",
                    "value": "order_status_query",
                },
            )
        )

        # 5. tag with relevant labels
        labeled = _body(
            await client.call_tool(
                "add_label",
                {
                    "conversation_id": target_id,
                    "labels": ["shipping", "auto-handled"],
                },
            )
        )
        assert set(labeled["labels"]) == {"shipping", "auto-handled"}

        # 6. reply to the contact
        reply = _body(
            await client.call_tool(
                "send_message",
                {
                    "conversation_id": target_id,
                    "content": (
                        "Hi! Order #4242 left the warehouse this "
                        "morning and is expected to arrive by Friday."
                    ),
                },
            )
        )
        assert reply["message_type"] == "outgoing"
        assert reply["sender_id"] == owner.user.id

        # 7. resolve
        resolved = _body(
            await client.call_tool(
                "resolve_conversation",
                {"conversation_id": target_id},
            )
        )
        assert resolved["status"] == "resolved"

    # ---- assertions on the resulting DB state -------------------------
    # The MCP middleware committed each tool's side-effects on its own
    # session. We re-read with the test fixture's session — but since
    # the fixture also commits, we need a fresh read transaction.
    async with mcp_session.bind.connect() as conn:
        # Use a one-shot session for assertions.
        sm = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with sm() as s:
            fresh = await s.get(Conversation, target_id)
            assert fresh is not None
            assert fresh.status == CONVERSATION_STATUS_RESOLVED
            assert (
                fresh.custom_attributes.get("intent")
                == "order_status_query"
            )
            assert set(
                t.strip()
                for t in (fresh.cached_label_list or "").split(",")
                if t.strip()
            ) == {"shipping", "auto-handled"}

            # The reply created an outgoing message.
            outgoing = list(
                (
                    await s.exec(
                        select(Message).where(
                            Message.conversation_id == target_id,
                            Message.message_type == MESSAGE_TYPE_OUTGOING,
                        )
                    )
                ).all()
            )
            assert len(outgoing) == 1
            assert "order #4242" in (outgoing[0].content or "").lower()

            # The full event cascade ran: Phase 7's reporting listener
            # wrote a conversation_resolved event.
            events = list(
                (
                    await s.exec(
                        select(ReportingEvent).where(
                            ReportingEvent.conversation_id == target_id,
                            ReportingEvent.name == "conversation_resolved",
                        )
                    )
                ).all()
            )
            assert len(events) == 1
            assert events[0].user_id is None  # no assignee on this conv


async def test_agent_handoff_via_set_ai_mode(mcp_session):
    """Common scenario: agent decides it can't handle the case and
    flips ``ai_mode`` to ``manual`` + drops a private note so the
    human takeover has context."""
    import secrets

    uniq = secrets.token_hex(4)
    owner = await AccountBuilder(
        mcp_session,
        AccountBuilderParams(
            email=f"admin-{uniq}@ho.mcp.example.com",
            account_name=f"Handoff-{uniq}",
            user_full_name="H Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            mcp_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox
    contact = Contact(account_id=owner.account.id, name="X")
    mcp_session.add(contact)
    await mcp_session.flush()
    ci = await ContactInboxBuilder(
        session=mcp_session,
        contact=contact,
        inbox=inbox,
        source_id=f"ho-{contact.id}",
    ).perform()
    conv = await create_conversation(
        mcp_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(
            additional_attributes={"ai_mode": "auto"},
        ),
    )
    token = await create_token(
        mcp_session,
        account_id=owner.account.id,
        name="agent",
        scope="write",
        user_id=owner.user.id,
    )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token.token

    mcp = build_server()
    async with Client(mcp) as client:
        # Agent encounters a complex case.
        _body(
            await client.call_tool(
                "add_private_note",
                {
                    "conversation_id": conv.id,
                    "content": (
                        "Escalating: customer is asking for a refund "
                        "outside the 30-day window. Needs manager approval."
                    ),
                },
            )
        )
        # Flip to manual.
        flipped = _body(
            await client.call_tool(
                "set_ai_mode",
                {"conversation_id": conv.id, "mode": "manual"},
            )
        )
        assert flipped["ai_mode"] == "manual"

    # Verify state.
    async with mcp_session.bind.connect() as conn:
        sm = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with sm() as s:
            fresh = await s.get(Conversation, conv.id)
            assert fresh is not None
            assert fresh.additional_attributes["ai_mode"] == "manual"
            # The private note landed as a message.
            notes = list(
                (
                    await s.exec(
                        select(Message).where(
                            Message.conversation_id == conv.id,
                            Message.private.is_(True),  # type: ignore[union-attr]
                        )
                    )
                ).all()
            )
            assert len(notes) == 1
            assert "Escalating" in (notes[0].content or "")
