"""The Free model: our llama-server, or a free hosted API (Groq, NVIDIA) with
a backup provider."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest
import respx

from app.core import local_llm
from app.core.config import get_settings
from app.domains.help_assistant import service as help_service

GROQ = "https://api.groq.com/openai/v1/chat/completions"
NVIDIA = "https://integrate.api.nvidia.com/v1/chat/completions"
LOCAL = "http://127.0.0.1:8092/v1/chat/completions"


def _reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.fixture
def hosted(monkeypatch) -> Iterator[None]:
    s = get_settings()
    monkeypatch.setattr(s, "local_llm_url", "https://api.groq.com/openai")
    monkeypatch.setattr(s, "local_llm_api_key", "gsk-test")
    monkeypatch.setattr(s, "local_llm_model", "openai/gpt-oss-20b")
    monkeypatch.setattr(s, "local_llm_fallback_url", "https://integrate.api.nvidia.com")
    monkeypatch.setattr(s, "local_llm_fallback_api_key", "nvapi-test")
    monkeypatch.setattr(s, "local_llm_fallback_model", "meta/llama-3.3-70b-instruct")
    yield


async def test_a_hosted_provider_gets_plain_openai(hosted):
    with respx.mock() as mock:
        route = mock.post(GROQ).mock(return_value=_reply('{"sabe": false}'))
        text, timings = await local_llm.chat(
            [{"role": "user", "content": "hola"}],
            max_tokens=50,
            json_schema={"type": "object"},
            slot=local_llm.HELP_SLOT,
        )
    assert text == '{"sabe": false}' and timings == {}
    request = route.calls[0].request
    sent = json.loads(request.content)
    assert request.headers["Authorization"] == "Bearer gsk-test"
    assert sent["model"] == "openai/gpt-oss-20b"
    assert sent["response_format"] == {"type": "json_object"}
    assert "cache_prompt" not in sent and "id_slot" not in sent
    assert "chat_template_kwargs" not in sent
    # JSON mode wants the word in the request.
    assert sent["messages"][0] == {"role": "system", "content": "Respond only with a JSON object."}


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(429, json={"error": "rate limit"}),
        httpx.Response(503),
        httpx.ReadTimeout("x"),
    ],
)
async def test_the_backup_answers_when_the_main_one_cannot(hosted, failure):
    with respx.mock() as mock:
        main = mock.post(GROQ)
        if isinstance(failure, Exception):
            main.mock(side_effect=failure)
        else:
            main.mock(return_value=failure)
        backup = mock.post(NVIDIA).mock(return_value=_reply("ok"))
        text, _ = await local_llm.chat([{"role": "user", "content": "hola"}], max_tokens=5)
    assert text == "ok"
    assert backup.calls[0].request.headers["Authorization"] == "Bearer nvapi-test"


async def test_when_both_refuse_the_limit_is_said(hosted):
    with respx.mock() as mock:
        mock.post(GROQ).mock(return_value=httpx.Response(429))
        mock.post(NVIDIA).mock(return_value=httpx.Response(429))
        with pytest.raises(local_llm.LocalLlmError) as caught:
            await local_llm.chat([{"role": "user", "content": "hola"}], max_tokens=5)
    assert caught.value.code == "rate_limited"


async def test_a_hosted_model_needs_no_slots_and_no_warming(hosted):
    assert await local_llm.slot_count() == 2
    assert await help_service.warm() is False


async def test_our_llama_server_keeps_its_extras(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "local_llm_url", "http://127.0.0.1:8092")
    monkeypatch.setattr(s, "local_llm_api_key", "")
    monkeypatch.setattr(s, "local_llm_fallback_url", "")
    with respx.mock() as mock:
        route = mock.post(LOCAL).mock(return_value=_reply("{}"))
        await local_llm.chat(
            [{"role": "user", "content": "hola"}],
            max_tokens=5,
            json_schema={"type": "object"},
            slot=local_llm.DECISIONS_SLOT,
        )
    sent = json.loads(route.calls[0].request.content)
    assert "Authorization" not in route.calls[0].request.headers
    assert sent["cache_prompt"] is True and sent["id_slot"] == local_llm.DECISIONS_SLOT
    assert sent["response_format"]["type"] == "json_schema"


@pytest.mark.parametrize(
    "text",
    ['{"sabe": true}', '```json\n{"sabe": true}\n```', '```\n{"sabe": true}\n```'],
)
def test_json_in_a_code_block_is_read(text):
    assert local_llm.parse_json(text) == {"sabe": True}
