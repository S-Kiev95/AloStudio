"""Installation-wide settings, editable from the dashboard.

The deployment story these serve: install AloStudio with nothing
configured, and fill in credentials from the UI as you obtain them —
never by editing a file on the server.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.installation import service
from app.domains.installation.models import InstallationConfig
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

CONFIGS = "/api/v1/installation/configs"


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


@pytest.fixture(autouse=True)
def _no_overlay_leaks():
    """A test that writes config must not change the next test's world."""
    service.reset_overlay()
    yield
    service.reset_overlay()


async def _seed(db_session, suffix: str, *, super_admin: bool = False):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@instconf.example.com",
            account_name=f"Inst{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
            super_admin=super_admin,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


def _find(payload: list[dict], name: str) -> dict:
    return next(c for c in payload if c["name"] == name)


# ---------------------------------------------------------------------------
# The empty install
# ---------------------------------------------------------------------------
async def test_a_fresh_install_lists_everything_as_unconfigured(
    client, db_session
):
    """Nothing set is a normal state, not an error."""
    _owner, headers = await _seed(db_session, "-fresh", super_admin=True)
    resp = await client.get(CONFIGS, headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()["payload"]

    assert {c["name"] for c in payload} >= {
        "META_APP_ID",
        "META_APP_SECRET",
        "META_INSTAGRAM_APP_ID",
        "META_OAUTH_REDIRECT_URI",
        "FB_VERIFY_TOKEN",
    }
    # Everything reports the environment until something overrides it.
    assert all(c["source"] == "environment" for c in payload)


async def test_setting_a_value_reaches_settings_immediately(
    client, db_session
):
    """The operator pastes an App ID and the OAuth flow can use it on the
    very next request — no restart."""
    _owner, headers = await _seed(db_session, "-set", super_admin=True)
    resp = await client.put(
        f"{CONFIGS}/META_APP_ID",
        headers=headers,
        json={"value": "1248493466251829"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["source"] == "database"
    assert get_settings().meta_app_id == "1248493466251829"


async def test_clearing_a_value_falls_back_to_the_environment(
    client, db_session, monkeypatch
):
    _owner, headers = await _seed(db_session, "-clear", super_admin=True)
    await client.put(
        f"{CONFIGS}/META_APP_ID", headers=headers, json={"value": "FROM-DB"}
    )
    assert get_settings().meta_app_id == "FROM-DB"

    resp = await client.delete(f"{CONFIGS}/META_APP_ID", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["source"] == "environment"
    assert get_settings().meta_app_id != "FROM-DB"


async def test_a_boolean_config_round_trips_as_a_boolean(client, db_session):
    _owner, headers = await _seed(db_session, "-bool", super_admin=True)
    resp = await client.put(
        f"{CONFIGS}/META_VERIFY_WEBHOOK_SIGNATURE",
        headers=headers,
        json={"value": True},
    )
    assert resp.status_code == 200, resp.text
    assert get_settings().meta_verify_webhook_signature is True

    await client.put(
        f"{CONFIGS}/META_VERIFY_WEBHOOK_SIGNATURE",
        headers=headers,
        json={"value": "false"},
    )
    assert get_settings().meta_verify_webhook_signature is False


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------
async def test_a_secret_is_never_echoed_back(client, db_session):
    """The operator needs to tell 'wrong one' from 'nothing', no more."""
    _owner, headers = await _seed(db_session, "-secret", super_admin=True)
    secret = "abc123def456ghi789"
    await client.put(
        f"{CONFIGS}/META_APP_SECRET", headers=headers, json={"value": secret}
    )

    resp = await client.get(CONFIGS, headers=headers)
    shown = _find(resp.json()["payload"], "META_APP_SECRET")
    assert secret not in resp.text
    assert shown["configured"] is True
    assert shown["value"].startswith("abc")
    assert shown["value"].endswith("89")
    assert "•" in shown["value"]


async def test_an_unset_secret_reads_as_empty_not_as_dots(client, db_session):
    _owner, headers = await _seed(db_session, "-nosecret", super_admin=True)
    resp = await client.get(CONFIGS, headers=headers)
    shown = _find(resp.json()["payload"], "IG_VERIFY_TOKEN")
    if not get_settings().ig_verify_token:
        assert shown["value"] == ""
        assert shown["configured"] is False


# ---------------------------------------------------------------------------
# What may be written
# ---------------------------------------------------------------------------
async def test_an_undeclared_name_is_refused(client, db_session):
    """The screen must not be able to inject a setting the code doesn't
    read — or, worse, one it does (DATABASE_URL)."""
    _owner, headers = await _seed(db_session, "-unknown", super_admin=True)
    resp = await client.put(
        f"{CONFIGS}/DATABASE_URL",
        headers=headers,
        json={"value": "postgresql://evil/"},
    )
    assert resp.status_code == 422
    assert "no es una configuración conocida" in resp.json()["message"]


async def test_a_locked_row_is_not_editable(client, db_session):
    _owner, headers = await _seed(db_session, "-locked", super_admin=True)
    db_session.add(
        InstallationConfig(
            name="META_APP_ID", serialized_value={"value": "x"}, locked=True
        )
    )
    await db_session.flush()

    resp = await client.put(
        f"{CONFIGS}/META_APP_ID", headers=headers, json={"value": "y"}
    )
    assert resp.status_code == 422
    assert "bloqueada" in resp.json()["message"]


async def test_an_undeclared_row_never_reaches_settings(db_session):
    """Rows the registry doesn't know about are inert, not injected."""
    db_session.add(
        InstallationConfig(
            name="DATABASE_URL",
            serialized_value={"value": "postgresql://evil/"},
            locked=False,
        )
    )
    await db_session.flush()
    overlay = await service.load_overlay(db_session)
    assert "database_url" not in overlay


# ---------------------------------------------------------------------------
# Who gets in
# ---------------------------------------------------------------------------
async def test_a_super_admin_gets_in(client, db_session):
    _owner, headers = await _seed(db_session, "-sa", super_admin=True)
    assert (await client.get(CONFIGS, headers=headers)).status_code == 200


async def test_an_agent_is_refused(client, db_session):
    """Not an administrator anywhere → no."""
    from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser

    await _seed(db_session, "-agent-owner", super_admin=True)
    other, other_headers = await _seed(db_session, "-agent")
    au = (
        await db_session.exec(
            select(AccountUser).where(AccountUser.user_id == other.user.id)
        )
    ).first()
    au.role = ACCOUNT_USER_ROLE_AGENT
    db_session.add(au)
    await db_session.flush()

    resp = await client.get(CONFIGS, headers=other_headers)
    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authorized"


# ---------------------------------------------------------------------------
# The bootstrap: a fresh install has no super admin at all
# ---------------------------------------------------------------------------
async def test_the_first_accounts_admin_gets_in_when_nobody_is_super_admin(
    client, db_session
):
    """Otherwise the settings screen is unreachable on exactly the
    install that needs it: the one deployed with no credentials."""
    from app.domains.installation.deps import has_any_super_admin

    _owner, headers = await _seed(db_session, "-boot")
    assert await has_any_super_admin(db_session) is False

    resp = await client.get(CONFIGS, headers=headers)
    assert resp.status_code == 200, resp.text


async def test_a_later_accounts_admin_does_not_get_the_bootstrap(
    client, db_session
):
    """The bootstrap is for the operator, not for every tenant admin."""
    await _seed(db_session, "-boot-first")
    _second, second_headers = await _seed(db_session, "-boot-second")

    resp = await client.get(CONFIGS, headers=second_headers)
    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authorized"


async def test_the_bootstrap_closes_once_a_super_admin_exists(
    client, db_session
):
    """Promoting a real super admin takes installation config away from
    the first account's admin — no lingering back door."""
    _first, first_headers = await _seed(db_session, "-boot-closes")
    assert (await client.get(CONFIGS, headers=first_headers)).status_code == 200

    await _seed(db_session, "-boot-real-sa", super_admin=True)

    resp = await client.get(CONFIGS, headers=first_headers)
    assert resp.status_code == 401
