"""The contact list must load what it presents — and no more.

``present_contact`` reads two things off a row that are not columns: the
contact's ``contact_inboxes`` and, through each of those, the ``inbox``.
Everything else in the payload is a column on ``contacts``.

That makes this list different from the reports, where narrowing the load
was free. Here a narrower load has a way to go wrong *silently*:
``_safe_contact_inboxes`` inspects the instance and returns ``[]`` when the
collection was never loaded — which is right for a freshly-created contact
with no rows, and wrong for a listed one. Nothing raises. The array just
comes back empty.

So the parity test comes first and is the important one; the counting test
only stops the list from paying for the rest of the schema.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

CONTACTS = 12

# Measured through the endpoints: six for the list, which also runs a count,
# and five for the search, which does not. Before the explicit loading they
# were sixteen and fifteen. Two queries of headroom.
MAX_QUERIES = 8


class QueryCounter:
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


@pytest.fixture
async def seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@ccost.example.com",
            account_name="CCost",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Bandeja",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox

    for i in range(CONTACTS):
        contact = Contact(
            account_id=owner.account.id,
            name=f"Contacto {i}",
            email=f"c{i}@ccost.example.com",
        )
        db_session.add(contact)
        await db_session.flush()
        await ContactInboxBuilder(
            session=db_session,
            contact=contact,
            inbox=inbox,
            source_id=f"src-{i}",
        ).perform()

    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, inbox, headers.as_response_headers()


async def test_the_list_still_carries_the_contact_inboxes(client, seeded):
    """The one a narrower load would break without raising.

    Both endpoints default to ``include_contact_inboxes=true``, so every
    row must carry a non-empty array with the inbox nested inside it.
    """
    owner, inbox, headers = seeded

    for url in (
        f"/api/v1/accounts/{owner.account.id}/contacts",
        f"/api/v1/accounts/{owner.account.id}/contacts/search?q=Contacto",
    ):
        resp = await client.get(url, headers=headers)
        assert resp.status_code == 200, resp.text
        payload = resp.json()["payload"]
        assert len(payload) == CONTACTS, url
        for row in payload:
            cis = row["contact_inboxes"]
            assert len(cis) == 1, f"{url}: {row['name']} vino con {len(cis)}"
            assert cis[0]["source_id"], url
            assert cis[0]["inbox"]["id"] == inbox.id, url
            assert cis[0]["inbox"]["name"] == "Bandeja", url


@pytest.mark.parametrize("path", ["contacts", "contacts/search?q=Contacto"])
async def test_the_list_costs_a_bounded_number_of_queries(
    client, seeded, counter, path
):
    owner, _inbox, headers = seeded

    counter.total = 0
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/{path}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["payload"]) == CONTACTS

    print(f"\n  /{path}: {counter.total} consultas para {CONTACTS} filas")
    assert counter.total <= MAX_QUERIES, (
        f"/{path} emitió {counter.total} consultas (tope {MAX_QUERIES}) "
        f"para {CONTACTS} contactos. Mirá los cargadores explícitos en "
        "app/domains/contacts/router.py."
    )
