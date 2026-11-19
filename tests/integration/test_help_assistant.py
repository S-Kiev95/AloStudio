"""The Ayuda button's endpoint, with the local model mocked (respx)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.help_assistant import service
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration

LLM = "http://llm.test:8092/v1/chat/completions"


class FakeModel:
    def __init__(self) -> None:
        self.replies: list[Any] = []
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": json.dumps(reply)}}],
                "timings": {"cache_n": 2400, "prompt_n": 12, "predicted_n": 40},
            },
        )


@pytest.fixture
def model(monkeypatch) -> Iterator[FakeModel]:
    monkeypatch.setattr(get_settings(), "local_llm_url", "http://llm.test:8092")
    fake = FakeModel()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(LLM).mock(side_effect=fake)
        yield fake


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _headers(db_session, user) -> dict[str, str]:
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@ayuda.example.com",
            account_name="Instituto",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent = (
        await AccountBuilder(
            db_session,
            AccountBuilderParams(
                email="sofia@ayuda.example.com",
                account_name="Otra",
                user_full_name="Sofía",
                user_password="Password123!",
                confirmed=True,
            ),
        ).perform()
    ).user
    db_session.add(
        AccountUser(account_id=owner.account.id, user_id=agent.id, role=ACCOUNT_USER_ROLE_AGENT)
    )
    await db_session.flush()
    return {
        "admin": owner.user,
        "agent": agent,
        "url": f"/api/v1/accounts/{owner.account.id}/help_assistant",
    }


CLOSING = {
    "sabe": True,
    "respuesta": 'Un administrador entra a Ajustes → Notas de cierre y marca "Obligatorio".',
    "pantalla": "ajustes_notas_cierre",
}


async def test_off_until_the_local_model_is_set(client, db_session, seeded, monkeypatch):
    monkeypatch.setattr(get_settings(), "local_llm_url", "")
    headers = await _headers(db_session, seeded["agent"])
    assert (await client.get(seeded["url"], headers=headers)).json()["enabled"] is False
    refused = await client.post(seeded["url"], json={"question": "hola"}, headers=headers)
    assert refused.json()["code"] == "help_assistant.disabled"


async def test_it_answers_with_the_screen_and_sends_the_cached_prefix(
    client, db_session, seeded, model
):
    headers = await _headers(db_session, seeded["admin"])
    model.replies.append(CLOSING)
    done = await client.post(
        seeded["url"],
        json={
            "question": "  como hago que pidan motivo al cerrar  ",
            "page": "/accounts/1/settings/lifecycle",
        },
        headers=headers,
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["known"] is True
    assert body["answer"] == CLOSING["respuesta"]
    assert body["screen"] == {
        "key": "ajustes_notas_cierre",
        "label": "Ajustes → Notas de cierre",
        "path": "settings/closing_notes",
    }

    sent = model.requests[-1]
    assert sent["cache_prompt"] is True
    assert sent["response_format"]["json_schema"]["schema"]["anyOf"][0]["required"] == ["sabe"]
    *prefix, question = sent["messages"]
    assert prefix == service.knowledge.prefix_messages()
    assert question == {
        "role": "user",
        "content": "Estoy en: Ajustes → Etapas del contacto\ncomo hago que pidan motivo al cerrar",
    }


async def test_an_agent_is_told_an_admin_does_it(client, db_session, seeded, model):
    headers = await _headers(db_session, seeded["agent"])
    model.replies.append(CLOSING)
    body = (
        await client.post(seeded["url"], json={"question": "motivo al cerrar"}, headers=headers)
    ).json()
    assert body["screen"] is None
    assert body["note"] == service.ADMIN_NOTE


async def test_not_knowing_and_invented_menus_get_the_fixed_reply(
    client, db_session, seeded, model
):
    headers = await _headers(db_session, seeded["admin"])
    model.replies.extend(
        [
            {"sabe": False},
            {
                "sabe": True,
                "respuesta": "Andá a Ajustes → Exportaciones y tocá Exportar.",
                "pantalla": "ninguna",
            },
        ]
    )
    for _ in range(2):
        body = (
            await client.post(seeded["url"], json={"question": "exportar a excel"}, headers=headers)
        ).json()
        assert body == {**body, "known": False, "answer": service.DONT_KNOW, "screen": None}

    empty = await client.post(seeded["url"], json={"question": "   "}, headers=headers)
    assert empty.json()["code"] == "help_assistant.question"


async def test_a_slow_model_says_it_is_getting_ready(client, db_session, seeded, model):
    headers = await _headers(db_session, seeded["admin"])
    model.replies.append(httpx.ReadTimeout("slow"))
    busy = await client.post(seeded["url"], json={"question": "hola"}, headers=headers)
    assert busy.status_code == 503
    assert busy.json()["code"] == "help_assistant.busy"
