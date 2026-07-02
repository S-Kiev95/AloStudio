"""Integration tests for the summary-report export (CSV + XLSX).

Anchor: ``app/domains/reporting/router.py`` (``/summary_reports/{scope}/export``)
plus the serialisers in ``app/core/exporters.py``.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
    update_labels,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
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


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@ex.example.com",
            account_name=f"EX{suffix}",
            user_full_name=f"Admin {suffix}",
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


def _base(account_id: int) -> str:
    return f"/api/v2/accounts/{account_id}/summary_reports"


async def test_export_requires_auth(client):
    resp = await client.get(f"{_base(1)}/agent/export")
    assert resp.status_code == 401


async def test_export_agent_csv_and_xlsx(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ce")

    # CSV (default format) — the admin lands as one row with their name.
    csv_resp = await client.get(f"{_base(owner.account.id)}/agent/export", headers=headers)
    assert csv_resp.status_code == 200, csv_resp.text
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert 'filename="reporte-agent.csv"' in csv_resp.headers["content-disposition"]
    text = csv_resp.content.decode("utf-8-sig")
    assert text.startswith("ID,Nombre,Conversaciones")
    assert "Admin" in text

    # XLSX — a valid single-sheet workbook carrying the same data.
    xlsx_resp = await client.get(
        f"{_base(owner.account.id)}/agent/export?format=xlsx", headers=headers
    )
    assert xlsx_resp.status_code == 200, xlsx_resp.text
    assert "spreadsheetml.sheet" in xlsx_resp.headers["content-type"]
    assert 'filename="reporte-agent.xlsx"' in xlsx_resp.headers["content-disposition"]
    zf = zipfile.ZipFile(io.BytesIO(xlsx_resp.content))
    assert "xl/worksheets/sheet1.xml" in zf.namelist()
    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Admin" in sheet and "Conversaciones" in sheet


async def test_export_label_scope_uses_row_names(client, db_session):
    owner, headers = await _seed_admin(db_session, "-lb")
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
    conv = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )
    await update_labels(db_session, conversation=conv, titles=["vip"])

    resp = await client.get(f"{_base(owner.account.id)}/label/export", headers=headers)
    assert resp.status_code == 200, resp.text
    text = resp.content.decode("utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == "ID,Nombre,Conversaciones,Resueltas,Resolución promedio (s),Primera respuesta promedio (s),Respuesta promedio (s)"
    # The label row carries the tag name + its conversation count.
    assert any(",vip," in ln and ln.rstrip().split(",")[2] == "1" for ln in lines[1:])


async def test_export_validation(client, db_session):
    owner, headers = await _seed_admin(db_session, "-vx")
    base = _base(owner.account.id)
    assert (await client.get(f"{base}/bogus/export", headers=headers)).status_code == 404
    bad_fmt = await client.get(f"{base}/agent/export?format=pdf", headers=headers)
    assert bad_fmt.status_code == 422
    assert "csv" in bad_fmt.json()["message"].lower()
