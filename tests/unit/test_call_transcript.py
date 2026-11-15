"""Reading Meta's call transcripts and asking for recordings (F7)."""

from __future__ import annotations

from app.core.models_registry import import_all_models
from app.domains.calls.models import CallInboxSettings
from app.domains.calls.whatsapp import media_request, parse_transcript

# Building a table model resolves every relationship in the registry.
import_all_models()


def test_segments_become_who_said_what() -> None:
    segments, language = parse_transcript(
        {
            "transcript": {
                "language": "es",
                "text": "[Business] Hola, CTC. [Customer] Quería saber del curso.",
                "segments": [
                    {"speaker": "Business", "channel": 0, "text": " Hola, CTC. ", "start": 0.4},
                    {"speaker": "Customer", "channel": 1, "text": "Quería saber del curso.", "start": 2},
                    {"speaker": "Customer", "channel": 1, "text": "   "},
                ],
            }
        }
    )
    assert language == "es"
    assert segments == [
        {"speaker": "business", "text": "Hola, CTC.", "start": 0.4},
        {"speaker": "customer", "text": "Quería saber del curso.", "start": 2.0},
    ]


def test_flat_text_is_split_by_its_markers() -> None:
    segments, _ = parse_transcript(
        {"transcript": {"text": "[Business] Buenas. [Customer] Hola, ¿cuánto sale? [Business] 4500."}}
    )
    assert [(s["speaker"], s["text"]) for s in segments] == [
        ("business", "Buenas."),
        ("customer", "Hola, ¿cuánto sale?"),
        ("business", "4500."),
    ]


def test_nothing_readable_gives_nothing() -> None:
    assert parse_transcript({"unexpected": True}) == ([], None)
    assert parse_transcript([]) == ([], None)


def test_accept_asks_for_what_the_inbox_chose() -> None:
    assert media_request(None) == {}
    plan = CallInboxSettings(
        inbox_id=1,
        account_id=1,
        record=True,
        transcribe=False,
        purpose="seguimiento de tu inscripción",
        announcement_language="es",
    )
    assert media_request(plan) == {
        "recording": {
            "status": "ENABLED",
            "purpose": "seguimiento de tu inscripción",
            "announcement_language": "es",
        }
    }
    plan.transcribe = True
    assert set(media_request(plan)) == {"recording", "transcription"}
