"""Unit tests for AI email template & signature generation (with respx).

Covers:
  * Free model (``local_llm``) generation returning sanitized HTML + notes.
  * Fast model (OpenAI ``llm.chat_completion``) when account enables Fast.
  * Reference screenshot described via ``media_ai.describe`` (NVIDIA / Groq)
    and fed into the text prompt.
  * Malicious markup from the LLM is sanitized before returning.
  * Missing ``{{contenido}}`` is automatically injected for templates, and
    stray ``{{contenido}}`` is stripped for signatures.
  * When all providers fail or none is configured, raises ``ai_down`` with
    the exact user-facing message.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.domains.email.ai_design import (
    AI_DOWN_MESSAGE,
    EmailAiError,
    generate_email_design,
)

pytestmark = pytest.mark.unit

TINY_PNG_B64 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()
TINY_PNG_DATA_URL = f"data:image/png;base64,{TINY_PNG_B64}"


def _account(*, fast: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=42,
        settings={"help_assistant": {"fast": fast}},
    )


def _configure(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    defaults = {
        "openai_api_key": "",
        "openai_base_url": "https://api.openai.com",
        "openai_agent_model": "gpt-4o-mini",
        "local_llm_url": "",
        "local_llm_api_key": "",
        "local_llm_model": "",
        "local_llm_fallback_url": "",
        "local_llm_fallback_api_key": "",
        "local_llm_fallback_model": "",
    }
    defaults.update(overrides)
    s = get_settings()
    for key, val in defaults.items():
        monkeypatch.setattr(s, key, val)


@respx.mock
async def test_free_model_generates_sanitized_template(monkeypatch):
    _configure(
        monkeypatch,
        local_llm_url="https://api.groq.com/openai",
        local_llm_api_key="groq-test-key",
        local_llm_model="llama-3.3-70b",
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"html": "<table style=\\"width:600px\\">'
                                '<tr><td onclick=\\"alert(1)\\"><script>evil()</script>'
                                '{{contenido}}</td></tr></table>", '
                                '"notes": "Membrete azul limpio."}'
                            )
                        }
                    }
                ]
            },
        )
    )

    result = await generate_email_design(
        AsyncMock(),
        account=_account(fast=False),
        prompt="Membrete azul corporativo",
        kind="template",
    )

    assert result.mode == "free"
    assert "{{contenido}}" in result.html
    assert "<script" not in result.html.lower()
    assert "onclick" not in result.html.lower()
    assert result.notes == "Membrete azul limpio."


@respx.mock
async def test_template_missing_contenido_gets_it_appended(monkeypatch):
    _configure(
        monkeypatch,
        local_llm_url="https://api.groq.com/openai",
        local_llm_api_key="groq-test-key",
        local_llm_model="llama-3.3-70b",
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"html": "<table><tr><td>Encabezado</td></tr></table>", "notes": "Listo."}'
                        }
                    }
                ]
            },
        )
    )

    result = await generate_email_design(
        AsyncMock(),
        account=_account(fast=False),
        prompt="Encabezado simple",
        kind="template",
    )

    assert "{{contenido}}" in result.html
    assert "Encabezado" in result.html


@respx.mock
async def test_signature_strips_stray_contenido_placeholder(monkeypatch):
    _configure(
        monkeypatch,
        local_llm_url="https://api.groq.com/openai",
        local_llm_api_key="groq-test-key",
        local_llm_model="llama-3.3-70b",
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"html": "<table><tr><td>{{nombre}} — {{cargo}}{{contenido}}</td></tr></table>", '
                                '"notes": "Firma compacta."}'
                            )
                        }
                    }
                ]
            },
        )
    )

    result = await generate_email_design(
        AsyncMock(),
        account=_account(fast=False),
        prompt="Firma minimalista con nombre y cargo",
        kind="signature",
    )

    assert "{{nombre}}" in result.html
    assert "{{cargo}}" in result.html
    assert "{{contenido}}" not in result.html


@respx.mock
async def test_reference_image_is_described_with_media_ai_and_passed_to_prompt(
    monkeypatch,
):
    _configure(
        monkeypatch,
        local_llm_url="https://integrate.api.nvidia.com",
        local_llm_api_key="nv-test-key",
        local_llm_model="meta/llama-3.3-70b",
    )
    vision_route = respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=[
            # First call: media_ai.describe (vision)
            httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "Encabezado azul marino con logo a la izquierda y pie gris."
                            }
                        }
                    ]
                },
            ),
            # Second call: local_llm.chat (HTML generation)
            httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"html": "<div style=\\"background:#002244\\">'
                                    '{{logo}}{{contenido}}</div>", '
                                    '"notes": "Inspirado en tu captura."}'
                                )
                            }
                        }
                    ]
                },
            ),
        ]
    )

    result = await generate_email_design(
        AsyncMock(),
        account=_account(fast=False),
        prompt="",
        image=TINY_PNG_DATA_URL,
        kind="template",
    )

    assert vision_route.call_count == 2
    assert result.seen == "Encabezado azul marino con logo a la izquierda y pie gris."
    assert "{{contenido}}" in result.html
    # The visual description must have been sent in the text prompt.
    second_body = vision_route.calls[1].request.content.decode()
    assert "Encabezado azul marino" in second_body


@respx.mock
async def test_fast_mode_uses_openai_when_allowed(monkeypatch):
    _configure(
        monkeypatch,
        openai_api_key="sk-test-openai",
        openai_base_url="https://api.openai.com",
    )
    # Stub budget check & usage recording so unit test stays DB-free.
    monkeypatch.setattr(
        "app.domains.email.ai_design.ai_budget_reached", AsyncMock(return_value=False)
    )
    monkeypatch.setattr("app.domains.usage.ai.ai_budget_reached", AsyncMock(return_value=False))
    monkeypatch.setattr("app.domains.usage.ai.record_ai_call", lambda *args, **kwargs: None)

    openai_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini",
                "usage": {"prompt_tokens": 100, "completion_tokens": 200},
                "choices": [
                    {
                        "message": {
                            "content": '{"html": "<div>{{contenido}}</div>", "notes": "Hecho con Fast."}'
                        }
                    }
                ],
            },
        )
    )

    result = await generate_email_design(
        AsyncMock(),
        account=_account(fast=True),
        prompt="Plantilla moderna",
        kind="template",
    )

    assert openai_route.called
    assert result.mode == "fast"
    assert "{{contenido}}" in result.html


@respx.mock
async def test_all_providers_failing_raises_ai_down(monkeypatch):
    _configure(
        monkeypatch,
        local_llm_url="https://api.groq.com/openai",
        local_llm_api_key="groq-test-key",
        local_llm_model="llama-3.3-70b",
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(503, text="overloaded")
    )

    with pytest.raises(EmailAiError) as exc_info:
        await generate_email_design(
            AsyncMock(),
            account=_account(fast=False),
            prompt="Membrete verde",
            kind="template",
        )

    assert exc_info.value.code == "ai_down"
    assert exc_info.value.status_code == 503
    assert exc_info.value.message == AI_DOWN_MESSAGE


async def test_no_provider_configured_raises_ai_down(monkeypatch):
    _configure(monkeypatch)

    with pytest.raises(EmailAiError) as exc_info:
        await generate_email_design(
            AsyncMock(),
            account=_account(fast=False),
            prompt="Membrete verde",
            kind="template",
        )

    assert exc_info.value.code == "ai_down"
    assert exc_info.value.message == "Servicios de AI temporalmente fuera, intenta mañana"
