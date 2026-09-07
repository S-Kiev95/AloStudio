"""The four entity summaries must not pay for object graphs they never read.

Each one runs its aggregates and then lists the entities so that rows with
no activity still appear — every agent, team, inbox and label in the
account. Those listings were plain ``select(Model)`` statements, and every
relationship in this codebase is declared ``lazy="selectin"``, so each of
them also fetched things the loops never touch: an AccountUser's user and
account, an Inbox's channel row and members. The loops read two columns.

Counted through the endpoint on purpose. An earlier test of this kind
rebuilt the statement with the same options and would have passed with the
fix deleted — it tested the list of relations, not the code that uses it.

Checked by reverting the fix: agent, team and inbox fail (inbox goes from
five queries to ten). **Label does not**, and it is worth saying so
rather than implying four guarded cases — ``Label`` declares no
relationships at all, so the narrower loading is a no-op there today. The
option stays on that statement for the day someone gives it one, and this
test starts guarding it then.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.labels.models import Label
from app.domains.teams.models import Team
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration

# Five, measured, for all four: two to authenticate, two aggregates and one
# listing. One query of headroom and no more — these counts are fixed by the
# code path and not by the data, so a relationship that goes back to loading
# eagerly is exactly one query more, and that is the thing to catch. If you
# add an aggregate on purpose, raise this number and say why.
MAX_QUERIES = 6


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
async def account(db_session):
    """An account with two of everything the summaries list."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@repcost.example.com",
            account_name="RepCost",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    mate = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@repcost.example.com",
            account_name="RepCost Vecina",
            user_full_name="Agente",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=mate.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    for name in ("API uno", "API dos"):
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name=name,
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    for name in ("soporte", "ventas"):
        db_session.add(Team(account_id=owner.account.id, name=name))
        db_session.add(Label(account_id=owner.account.id, title=name))

    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


@pytest.mark.parametrize("scope", ["agent", "team", "inbox", "label"])
async def test_the_summary_costs_a_bounded_number_of_queries(
    client, account, counter, scope
):
    owner, headers = account

    counter.total = 0
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/summary_reports/{scope}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 2, f"el informe de {scope} devolvió {len(rows)} filas"

    print(f"\n  informe de {scope}: {counter.total} consultas")
    assert counter.total <= MAX_QUERIES, (
        f"el informe de {scope} emitió {counter.total} consultas (tope "
        f"{MAX_QUERIES}) para dos filas. Suele ser el listado de entidades "
        "sin ``lazyload('*')``: mirá "
        "app/domains/reporting/summary_builders.py."
    )


async def test_the_entity_names_survive_the_narrower_loading(client, account):
    """Loading less must not present less.

    ``name`` is the only field in these payloads that does not come from an
    aggregate, so it is the one a narrower load could quietly empty.
    """
    owner, headers = account
    for scope, expected in (
        ("team", {"soporte", "ventas"}),
        ("inbox", {"API uno", "API dos"}),
        ("label", {"soporte", "ventas"}),
    ):
        resp = await client.get(
            f"/api/v2/accounts/{owner.account.id}/summary_reports/{scope}",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert {r["name"] for r in resp.json()} == expected, scope
