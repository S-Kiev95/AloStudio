"""Signatures and sets: the composer's saved texts and saved composers."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.media_library.models import MediaAsset
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app
from tests.integration._publishing import channel_id_of

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


async def _headers(db_session, user) -> dict[str, str]:
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@presets.example.com",
            account_name=f"PRE{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    return owner, await _headers(db_session, owner.user)


async def _agent_headers(db_session, account_id: int, suffix: str):
    other = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@presets.example.com",
            account_name=f"PREAGENT{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(account_id=account_id, user_id=other.user.id, role=ACCOUNT_USER_ROLE_AGENT)
    )
    await db_session.flush()
    return await _headers(db_session, other.user)


async def _page_channel(db_session, account, suffix: str) -> int:
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=account,
                name=f"Pagina {suffix}",
                channel_type="facebook",
                channel_params={"page_id": f"PG{suffix}", "page_access_token": "t"},
            ),
        ).perform()
    ).inbox
    return await channel_id_of(db_session, inbox)


async def _asset(db_session, account_id: int, key: str) -> MediaAsset:
    asset = MediaAsset(
        account_id=account_id,
        kind="image",
        key=key,
        filename="foto.jpg",
        content_type="image/jpeg",
        size_bytes=1000,
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------
async def test_signatures_crud_and_a_single_auto_add(client, db_session):
    owner, h = await _seed(db_session, "-sig")
    url = f"/api/v1/accounts/{owner.account.id}/publications/signatures"

    first = (await client.post(url, headers=h, json={"content": "Tel 099 123 456", "auto_add": True})).json()
    second = (await client.post(url, headers=h, json={"content": "#estetica #salto"})).json()
    assert first["auto_add"] is True and second["auto_add"] is False

    r = await client.patch(f"{url}/{second['id']}", headers=h, json={"auto_add": True})
    assert r.status_code == 200 and r.json()["auto_add"] is True
    listed = (await client.get(url, headers=h)).json()
    assert [(s["id"], s["auto_add"]) for s in listed] == [(first["id"], False), (second["id"], True)]

    r = await client.patch(f"{url}/{first['id']}", headers=h, json={"content": "Tel 099 000 000"})
    assert r.json()["content"] == "Tel 099 000 000"
    assert (await client.post(url, headers=h, json={"content": ""})).status_code == 422

    assert (await client.delete(f"{url}/{first['id']}", headers=h)).status_code == 200
    assert [s["id"] for s in (await client.get(url, headers=h)).json()] == [second["id"]]


async def test_signatures_are_per_account_and_admin_only(client, db_session):
    owner, h = await _seed(db_session, "-sig2")
    other, other_h = await _seed(db_session, "-sig3")
    agent_h = await _agent_headers(db_session, owner.account.id, "-sig2")
    url = f"/api/v1/accounts/{owner.account.id}/publications/signatures"
    created = (await client.post(url, headers=h, json={"content": "Firma"})).json()

    assert (await client.get(url, headers=agent_h)).status_code == 200
    assert (await client.post(url, headers=agent_h, json={"content": "x"})).status_code == 401
    foreign = f"/api/v1/accounts/{other.account.id}/publications/signatures/{created['id']}"
    assert (await client.patch(foreign, headers=other_h, json={"content": "y"})).status_code == 404


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------
async def test_sets_crud(client, db_session):
    owner, h = await _seed(db_session, "-set")
    channel_id = await _page_channel(db_session, owner.account, "set")
    asset = await _asset(db_session, owner.account.id, "acct/set/foto.jpg")
    url = f"/api/v1/accounts/{owner.account.id}/publications/sets"

    r = await client.post(
        url,
        headers=h,
        json={
            "name": "Promo semanal",
            "content": "Esta semana…",
            "media": [{"media_id": asset.id}, {"type": "image", "url": "https://cdn.example.com/x.jpg"}],
            "targets": [{"channel_id": channel_id, "settings": {}, "content_override": "Solo FB"}],
        },
    )
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["name"] == "Promo semanal"
    assert created["media"][0]["media_id"] == asset.id and created["media"][0]["type"] == "image"
    assert created["media"][0]["url"]
    assert created["media"][1] == {"type": "image", "url": "https://cdn.example.com/x.jpg"}
    (target,) = created["targets"]
    assert target["channel_id"] == channel_id and target["channel"]["network"] == "facebook_page"
    assert target["content_override"] == "Solo FB"

    r = await client.patch(f"{url}/{created['id']}", headers=h, json={"name": "Promo", "targets": []})
    updated = r.json()
    assert (updated["name"], updated["targets"], updated["content"]) == ("Promo", [], "Esta semana…")
    assert len(updated["media"]) == 2

    assert [s["name"] for s in (await client.get(url, headers=h)).json()] == ["Promo"]
    assert (await client.delete(f"{url}/{created['id']}", headers=h)).status_code == 200
    assert (await client.get(url, headers=h)).json() == []


async def test_sets_only_take_the_accounts_channels_and_files(client, db_session):
    owner, h = await _seed(db_session, "-set2")
    other, _other_h = await _seed(db_session, "-set3")
    foreign_channel = await _page_channel(db_session, other.account, "set3")
    foreign_asset = await _asset(db_session, other.account.id, "acct/set3/foto.jpg")
    url = f"/api/v1/accounts/{owner.account.id}/publications/sets"

    for body in (
        {"name": "x", "targets": [{"channel_id": foreign_channel}]},
        {"name": "x", "media": [{"media_id": foreign_asset.id}]},
        {"name": "x", "media": [{"type": "pdf", "url": "https://x"}]},
        {"name": "   "},
    ):
        r = await client.post(url, headers=h, json=body)
        assert r.status_code == 422, (body, r.text)


async def test_signature_and_set_routes_dont_clash_with_publications(client, db_session):
    owner, h = await _seed(db_session, "-routes")
    base = f"/api/v1/accounts/{owner.account.id}/publications"

    assert (await client.get(f"{base}/signatures", headers=h)).status_code == 200
    assert (await client.get(f"{base}/sets", headers=h)).status_code == 200
    assert (await client.get(f"{base}/999999", headers=h)).status_code == 404
