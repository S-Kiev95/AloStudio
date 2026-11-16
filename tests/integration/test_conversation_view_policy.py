"""Opening one conversation checks who is asking (``ConversationPolicy#show?``).

The list was scoped to the agent's inboxes, but every endpoint that loads a
single conversation by number — its messages, its details, its actions —
only checked the account. Any member could read any conversation by
guessing ``/conversations/7/messages``. Chatwoot runs ``show?`` on all of
them: administrator, or member of the conversation's inbox, or of its team.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import MESSAGE_TYPE_INCOMING, Conversation, Message
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams.models import Team, TeamMember
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
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


async def _builder(db_session, suffix):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"u{suffix}@politica.example.com",
            account_name=f"Pol{suffix}",
            user_full_name=f"U{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _headers(db_session, user):
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def world(db_session):
    owner = await _builder(db_session, "admin")
    account = owner.account
    ventas = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=account, name="Ventas", channel_type="api",
                channel_params={"webhook_url": ""},
            ),
        ).perform()
    ).inbox
    equipo = Team(account_id=account.id, name="Cobranzas")
    db_session.add(equipo)
    contact = Contact(account_id=account.id, name="Ana")
    db_session.add(contact)
    await db_session.flush()
    ci = ContactInbox(contact_id=contact.id, inbox_id=ventas.id, source_id="pol-1")
    db_session.add(ci)
    await db_session.flush()
    conv = Conversation(
        account_id=account.id, inbox_id=ventas.id, contact_id=contact.id,
        contact_inbox_id=ci.id, display_id=1, team_id=equipo.id,
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(conv)
    db_session.add(
        Message(
            account_id=account.id, inbox_id=ventas.id, conversation_id=conv.id,
            message_type=MESSAGE_TYPE_INCOMING, content="dato sensible",
        )
    )

    async def agent(suffix, *, inbox=False, team=False):
        u = (await _builder(db_session, suffix)).user
        db_session.add(
            AccountUser(account_id=account.id, user_id=u.id, role=ACCOUNT_USER_ROLE_AGENT)
        )
        if inbox:
            db_session.add(InboxMember(inbox_id=ventas.id, user_id=u.id))
        if team:
            db_session.add(TeamMember(team_id=equipo.id, user_id=u.id))
        await db_session.flush()
        return await _headers(db_session, u)

    return {
        "base": f"/api/v1/accounts/{account.id}/conversations/{conv.display_id}",
        "admin": await _headers(db_session, owner.user),
        "ajeno": await agent("ajeno"),
        "bandeja": await agent("bandeja", inbox=True),
        "equipo": await agent("equipo", team=True),
    }


@pytest.mark.parametrize("path", ["/messages", ""])
async def test_an_agent_outside_the_inbox_and_team_is_refused(client, world, path):
    resp = await client.get(world["base"] + path, headers=world["ajeno"])
    assert resp.status_code == 401
    # The code keeps the browser from reading this as an expired session.
    assert resp.json()["code"] == "not_authorized"
    assert "dato sensible" not in resp.text


@pytest.mark.parametrize("who", ["admin", "bandeja", "equipo"])
async def test_admin_inbox_member_and_team_member_can_read(client, world, who):
    resp = await client.get(world["base"] + "/messages", headers=world[who])
    assert resp.status_code == 200, resp.text
    assert "dato sensible" in resp.text
