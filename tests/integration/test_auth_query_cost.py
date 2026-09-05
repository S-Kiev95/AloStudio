"""Authenticating must stay cheap: it runs on every single request.

Measured against staging on 2026-09-05, every account-scoped endpoint
opened with the same three tables — ``users``, ``account_users``,
``accounts`` — including ones that return a flat list with no
relationships at all. It was not each endpoint's own fan-out. It was
eleven queries of *authentication*, per request: four to answer "who is
this" (the User, its memberships, each membership's account, each of
those accounts' whole member list) and seven more to resolve the account
and the caller's role.

Every relationship in this codebase is declared ``lazy="selectin"``, so
loading one row pulls a connected component of the schema. The auth path
turns that off for its two statements, which is safe only because
nothing reads a relationship off either object — see
``present_agent``, which used to be the one exception.

The labels index is the canary: there is nothing in it but one select
for the rows. Whatever this test counts above that is the price of
knowing who is calling.
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
from app.domains.labels.models import Label
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

# Three on staging: the User, the account+membership join, the labels.
# The margin is for a fixture-shaped difference, not for a new eager
# load — twelve is what this exists to catch, and anything that walks a
# relationship off the User or the Account lands well above six.
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


async def test_a_flat_endpoint_pays_almost_nothing_to_authenticate(
    client, db_session, counter
):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@authcost.example.com",
            account_name="AuthCost",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    for name in ("urgente", "ventas", "soporte"):
        db_session.add(Label(account_id=owner.account.id, title=name))
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()

    counter.total = 0
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/labels",
        headers=headers.as_response_headers(),
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["payload"]) == 3

    print(f"\n  la lista de etiquetas costó {counter.total} consultas")
    assert counter.total <= MAX_QUERIES, (
        f"una petición autenticada emitió {counter.total} consultas "
        f"(tope {MAX_QUERIES}) para devolver tres etiquetas. Casi seguro "
        "es la autenticación cargando el grafo del usuario o de la cuenta: "
        "mirá las opciones de las dos consultas de app/core/deps.py."
    )
