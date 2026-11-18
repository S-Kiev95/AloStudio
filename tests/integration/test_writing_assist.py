"""AI help while writing (F17): the composer's AI button rewrites the draft and
summarizes the conversation. OpenAI is mocked with respx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_TYPE_ACTIVITY,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Message,
)
from app.domains.conversations.service import ConversationBuilderParams, create_conversation
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.usage.limits import set_limit
from app.domains.usage.models import KIND_AI, UsageRecord
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration

OPENAI = "https://api.openai.com/v1/chat/completions"


class FakeOpenAI:
    """Answers each completion with the next scripted text and keeps what was
    asked."""

    def __init__(self) -> None:
        self.replies: list[str] = []
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        if not self.replies:
            return httpx.Response(500, json={"error": {"message": "no scripted reply"}})
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.4-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": self.replies.pop(0)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 200, "completion_tokens": 50},
            },
        )

    def prompt(self, index: int = -1) -> tuple[str, str]:
        """(system, user) of a request."""
        messages = self.requests[index]["messages"]
        return messages[0]["content"], messages[1]["content"]


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


@pytest.fixture
def openai(monkeypatch) -> Iterator[FakeOpenAI]:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.openai.com")
    monkeypatch.setattr(settings, "ai_writing_assist_enabled", True)
    fake = FakeOpenAI()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(OPENAI).mock(side_effect=fake)
        yield fake


async def _headers(db_session, user) -> dict[str, str]:
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


async def _user(db_session, name: str, email: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=email,
            account_name=f"Cuenta de {name}",
            user_full_name=name,
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


@pytest.fixture
async def seeded(db_session):
    owner = await _user(db_session, "Admin", "admin@assist.example.com")
    account = owner.account
    sofia = (await _user(db_session, "Sofía", "sofia@assist.example.com")).user
    outsider = (await _user(db_session, "Pablo", "pablo@assist.example.com")).user
    for user in (sofia, outsider):
        db_session.add(
            AccountUser(account_id=account.id, user_id=user.id, role=ACCOUNT_USER_ROLE_AGENT)
        )
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=account,
                name="Web",
                channel_type="api",
                channel_params={"webhook_url": "https://example.com/h"},
            ),
        ).perform()
    ).inbox
    db_session.add(InboxMember(inbox_id=inbox.id, user_id=sofia.id))
    contact = Contact(account_id=account.id, name="Lucía Pereira")
    db_session.add(contact)
    await db_session.flush()
    contact_inbox = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox
    ).perform()
    await db_session.refresh(contact_inbox, ["inbox"])
    conversation = await create_conversation(
        db_session, contact_inbox=contact_inbox, params=ConversationBuilderParams()
    )
    return {
        "account": account,
        "sofia": sofia,
        "outsider": outsider,
        "inbox": inbox,
        "contact": contact,
        "conversation": conversation,
        "url": f"/api/v1/accounts/{account.id}/writing_assist",
    }


def _message(seeded, message_type: int, content: str | None, **extra: Any) -> Message:
    return Message(
        account_id=seeded["account"].id,
        inbox_id=seeded["inbox"].id,
        conversation_id=seeded["conversation"].id,
        message_type=message_type,
        content=content,
        **extra,
    )


async def _usage(db_session, account_id: int) -> list[UsageRecord]:
    await db_session.flush()  # the request's commit would; the test session does not
    return list(
        (
            await db_session.exec(
                select(UsageRecord).where(
                    UsageRecord.account_id == account_id, UsageRecord.kind == KIND_AI
                )
            )
        ).all()
    )


async def test_it_stays_off_until_the_operator_turns_it_on(client, db_session, seeded, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "ai_writing_assist_enabled", False)
    headers = await _headers(db_session, seeded["sofia"])

    shown = (await client.get(seeded["url"], headers=headers)).json()
    assert shown["enabled"] is False
    assert shown["actions"] == [
        "improve",
        "fix",
        "formal",
        "friendly",
        "shorter",
        "translate",
        "summarize",
    ]
    assert "es" in shown["languages"] and "en" in shown["languages"]
    refused = await client.post(
        seeded["url"], json={"action": "improve", "text": "hola"}, headers=headers
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "writing_assist.disabled"

    # On without a key is still off.
    monkeypatch.setattr(settings, "ai_writing_assist_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert (await client.get(seeded["url"], headers=headers)).json()["enabled"] is False
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    assert (await client.get(seeded["url"], headers=headers)).json()["enabled"] is True


async def test_the_draft_comes_back_rewritten_and_the_spend_is_recorded(
    client, db_session, seeded, openai
):
    headers = await _headers(db_session, seeded["sofia"])
    draft = "hola lucia, el curso sale $ 2.500 por mes y empieza el {{1}}, te sirve?"
    openai.replies.append(
        '"Hola, Lucía. El curso sale $ 2.500 por mes y empieza el {{1}}. ¿Te sirve?"'
    )

    done = await client.post(
        seeded["url"], json={"action": "improve", "text": f"  {draft}\n"}, headers=headers
    )
    assert done.status_code == 200, done.text
    # The quotes the model put around it go away.
    assert done.json() == {
        "text": "Hola, Lucía. El curso sale $ 2.500 por mes y empieza el {{1}}. ¿Te sirve?"
    }
    system, user = openai.prompt()
    assert "{{1}}" in system and "vos" in system
    assert user.endswith(f"Draft:\n{draft}")
    assert "clear, natural" in user
    assert openai.requests[-1]["model"] == get_settings().openai_agent_model

    usage = await _usage(db_session, seeded["account"].id)
    assert [(u.category, u.input_tokens, u.output_tokens) for u in usage] == [
        ("writing_assist", 200, 50)
    ]


async def test_translate_names_the_language_and_bad_requests_say_why(
    client, db_session, seeded, openai
):
    headers = await _headers(db_session, seeded["sofia"])
    url = seeded["url"]
    openai.replies.append("Hi Lucía, the course is $2,500 a month.")

    done = await client.post(
        url,
        json={
            "action": "translate",
            "text": "Hola Lucía, el curso sale $ 2.500 por mes.",
            "language": "en",
        },
        headers=headers,
    )
    assert done.json()["text"] == "Hi Lucía, the course is $2,500 a month."
    assert "Translate it into English" in openai.prompt()[1]

    async def code(body: dict[str, Any]) -> str:
        response = await client.post(url, json=body, headers=headers)
        assert response.status_code == 422, response.text
        return response.json()["code"]

    assert await code({"action": "translate", "text": "hola", "language": "xx"}) == (
        "writing_assist.language"
    )
    assert await code({"action": "poem", "text": "hola"}) == "writing_assist.action"
    assert await code({"action": "fix", "text": "   "}) == "writing_assist.text"
    assert await code({"action": "fix", "text": "a" * 4001}) == "writing_assist.text"
    assert len(openai.requests) == 1, "nothing invalid reaches OpenAI"

    # OpenAI failing is said as such.
    assert await code({"action": "fix", "text": "hola"}) == "writing_assist.failed"


async def test_the_spend_cap_stops_it_before_calling(client, db_session, seeded, openai):
    await set_limit(db_session, seeded["account"].id, KIND_AI, 0)
    headers = await _headers(db_session, seeded["sofia"])
    refused = await client.post(
        seeded["url"], json={"action": "shorter", "text": "hola, ¿cómo andás?"}, headers=headers
    )
    assert refused.json()["code"] == "writing_assist.budget"
    assert openai.requests == []


async def test_the_summary_reads_the_conversation_for_who_can_see_it(
    client, db_session, seeded, openai
):
    sofia = seeded["sofia"]
    db_session.add_all(
        [
            _message(
                seeded,
                MESSAGE_TYPE_INCOMING,
                "Hola, ¿tienen inglés\nde noche?",
                sender_type="Contact",
                sender_id=seeded["contact"].id,
            ),
            _message(
                seeded,
                MESSAGE_TYPE_OUTGOING,
                "Sí, lunes y miércoles a las 20 h.",
                sender_type="User",
                sender_id=sofia.id,
            ),
            _message(
                seeded,
                MESSAGE_TYPE_OUTGOING,
                "Pidió precio, falta mandarlo",
                private=True,
                sender_type="User",
                sender_id=sofia.id,
            ),
            _message(seeded, MESSAGE_TYPE_ACTIVITY, "Conversación asignada a Sofía"),
            _message(seeded, MESSAGE_TYPE_INCOMING, None, sender_type="Contact"),
        ]
    )
    await db_session.flush()
    body = {
        "action": "summarize",
        "conversation_id": seeded["conversation"].display_id,
        "language": "pt",
    }

    outsider = await _headers(db_session, seeded["outsider"])
    hidden = await client.post(seeded["url"], json=body, headers=outsider)
    assert hidden.status_code == 404
    missing = await client.post(
        seeded["url"], json={**body, "conversation_id": 999999}, headers=outsider
    )
    assert missing.status_code == 404

    openai.replies.append("- Lucía quiere inglés de noche.\n- Falta mandarle el precio.")
    headers = await _headers(db_session, sofia)
    done = await client.post(seeded["url"], json=body, headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["text"].startswith("- Lucía quiere inglés")
    system, transcript = openai.prompt()
    assert "Write in Portuguese" in system
    assert transcript.splitlines() == [
        "Customer's name: Lucía Pereira",
        "Customer: Hola, ¿tienen inglés de noche?",
        "Agent (Sofía): Sí, lunes y miércoles a las 20 h.",
        "Internal note (Sofía): Pidió precio, falta mandarlo",
        "Customer: [attachment]",
    ]


async def test_an_empty_conversation_has_nothing_to_summarize(client, db_session, seeded, openai):
    headers = await _headers(db_session, seeded["sofia"])
    empty = await client.post(
        seeded["url"],
        json={"action": "summarize", "conversation_id": seeded["conversation"].display_id},
        headers=headers,
    )
    assert empty.json()["code"] == "writing_assist.conversation"
    assert openai.requests == []
