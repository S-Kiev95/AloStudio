"""The conversation list must not go back to costing 79 queries.

Every relationship in this codebase is declared ``lazy="selectin"``, so a
plain ``select(Conversation)`` pulls a large connected component of the
schema. Measured against staging with real data, one page of 25 emitted
**79 queries and ~300 ms** — 30 of them on ``users``, 15 on ``accounts``,
15 on ``account_users``, none of which appear in the payload.

The finder names what ``present_conversation`` reads and turns the eager
defaults off for that one statement. This pins the result, because the
regression is silent: adding a relationship, or reading a new one from
the presenter, costs a fan-out that nothing else would notice.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.finder import conversation_finder
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    Conversation,
    Message,
)
from app.domains.conversations.presenters import present_conversations_index
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

# Room above the measured floor (8 on staging) for the finder's four count
# queries and a fixture-shaped difference or two — but far below the 79
# this exists to catch. A number this loose still fails loudly on a
# fan-out, which is the only failure mode that matters here.
MAX_QUERIES = 20


class QueryCounter:
    """Counts statements on the session's engine for the duration of a
    block. Cheaper and more honest than timing: a query count is stable
    across machines, a millisecond figure is not."""

    def __init__(self) -> None:
        self.total = 0

    def __call__(self, conn, cursor, statement, params, context, executemany):
        self.total += 1


@pytest.fixture
def counter(db_session) -> Iterator[QueryCounter]:
    bind = db_session.get_bind()
    target = getattr(bind, "sync_engine", bind)
    c = QueryCounter()
    event.listen(target, "before_cursor_execute", c)
    try:
        yield c
    finally:
        event.remove(target, "before_cursor_execute", c)


async def _seed(db_session, *, conversations: int, messages_each: int):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@qcount.example.com",
            account_name="QCount",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    account = owner.account
    inbox_res = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=account,
            name="Bandeja",
            channel_type="api",
            channel_params={"webhook_url": ""},
        ),
    ).perform()
    inbox = inbox_res.inbox

    for i in range(conversations):
        contact = Contact(account_id=account.id, name=f"Contacto {i}")
        db_session.add(contact)
        await db_session.flush()
        ci = ContactInbox(
            contact_id=contact.id,
            inbox_id=inbox.id,
            source_id=f"src-{i}",
        )
        db_session.add(ci)
        await db_session.flush()
        conv = Conversation(
            account_id=account.id,
            inbox_id=inbox.id,
            contact_id=contact.id,
            contact_inbox_id=ci.id,
            display_id=i + 1,
        )
        db_session.add(conv)
        await db_session.flush()
        for j in range(messages_each):
            db_session.add(
                Message(
                    account_id=account.id,
                    inbox_id=inbox.id,
                    conversation_id=conv.id,
                    message_type=MESSAGE_TYPE_INCOMING,
                    content=f"mensaje {j}",
                )
            )
        await db_session.flush()

    return owner


async def test_the_list_costs_a_bounded_number_of_queries(db_session, counter):
    owner = await _seed(db_session, conversations=25, messages_each=3)
    counter.total = 0

    result = await conversation_finder(
        db_session,
        account_id=owner.account.id,
        current_user_id=owner.user.id,
        params={},
        page=1,
        per_page=25,
    )
    body = present_conversations_index(result["conversations"], **result["count"])

    assert len(body["data"]["payload"]) == 25
    print(f"\n  la lista costó {counter.total} consultas para 25 filas")
    assert counter.total <= MAX_QUERIES, (
        f"la lista emitió {counter.total} consultas (tope {MAX_QUERIES}). "
        "Suele ser una relación nueva con lazy='selectin', o el presentador "
        "leyendo algo que el finder no carga explícitamente."
    )


async def test_the_cost_does_not_grow_with_the_page_size(db_session, counter):
    """Guards a *different* failure from the one above: a true N+1.

    Worth stating plainly, because this test passes with or without the
    explicit loading — ``selectin`` batches per relationship, not per
    row, so the 79-query fan-out never grew with the page. What this
    catches is a relationship that falls back to ``lazy="select"``, or a
    presenter that queries per row: then 25 rows cost five times what 5
    rows do, and the bill only shows up in production.
    """
    owner = await _seed(db_session, conversations=25, messages_each=3)

    async def cost(per_page: int) -> int:
        db_session.expunge_all()
        counter.total = 0
        await conversation_finder(
            db_session,
            account_id=owner.account.id,
            current_user_id=owner.user.id,
            params={},
            page=1,
            per_page=per_page,
        )
        return counter.total

    pocas = await cost(5)
    muchas = await cost(25)
    assert muchas == pocas, (
        f"5 filas costaron {pocas} consultas y 25 costaron {muchas}: "
        "algo se carga por fila."
    )


async def test_the_payload_is_unchanged_by_the_explicit_loading(
    db_session, counter
):
    """Loading less must not present less.

    The fields at risk are exactly the ones that come from relationships:
    the sender, the channel, the last message, the unread count.
    """
    owner = await _seed(db_session, conversations=3, messages_each=2)
    result = await conversation_finder(
        db_session,
        account_id=owner.account.id,
        current_user_id=owner.user.id,
        params={},
        page=1,
        per_page=25,
    )
    payload = present_conversations_index(
        result["conversations"], **result["count"]
    )["data"]["payload"]

    assert len(payload) == 3
    for row in payload:
        assert row["meta"]["sender"] is not None, "el contacto no se cargó"
        assert row["meta"]["channel"] is not None, "la bandeja no se cargó"
        assert row["last_non_activity_message"] is not None, (
            "el último mensaje no se cargó"
        )
        assert row["unread_count"] == 2, "los mensajes no se cargaron"


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


async def test_the_message_list_costs_a_bounded_number_of_queries(
    client, db_session, counter
):
    """The worse of the two before this: 98 queries for 17 messages.

    Each message eagerly pulled its own account and inbox — the same rows
    over and over — plus the conversation back-reference and its graph.

    Goes through the HTTP endpoint on purpose. An earlier version of this
    rebuilt the same statement with the same options and would have
    passed with the router's ``.options(...)`` deleted — it tested the
    list of relations, not the code that uses it.
    """
    owner = await _seed(db_session, conversations=1, messages_each=20)
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()

    conv = (
        await db_session.exec(
            select(Conversation).where(
                Conversation.account_id == owner.account.id
            )
        )
    ).first()

    counter.total = 0
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/"
        f"{conv.display_id}/messages",
        headers=headers.as_response_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["payload"]) == 20

    print(f"\n  los mensajes costaron {counter.total} consultas para 20 filas")
    assert counter.total <= MAX_QUERIES, (
        f"la lista de mensajes emitió {counter.total} consultas "
        f"(tope {MAX_QUERIES})."
    )
