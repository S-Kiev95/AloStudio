"""Decisions (F10): what leaves the server, the questions, the answers."""

from __future__ import annotations

import pytest

from app.domains.decisions import local
from app.domains.decisions.anonymize import anonymize
from app.domains.decisions.client import parse
from app.domains.decisions.questions import (
    as_service_questions,
    clean,
    defaults,
    slug,
    team_options,
)


def test_identifying_details_come_out():
    text = (
        "Cliente: Hola, soy Lucía Pereira, mi cel es +598 99 123 456 y mi CI 4.567.890-1. "
        "Escribime a lucia.p@gmail.com o mirá https://ctc.edu.uy/cursos. ¿El curso de 4500 empieza a las 19?"
    )
    out = anonymize(text, ["Lucía Pereira", "Sofía"])
    assert "Lucía" not in out and "Pereira" not in out
    assert "[nombre]" in out
    assert "+598" not in out and "4.567.890-1" not in out
    assert "lucia.p@gmail.com" not in out and "[correo]" in out
    assert "https://" not in out and "[enlace]" in out
    # Prices and hours identify nobody and matter to the question.
    assert "4500" in out and "19" in out


def test_short_names_and_numbers_are_left_alone():
    assert anonymize("Agente: Hola Al, son 2 cuotas", ["Al"]) == "Agente: Hola Al, son 2 cuotas"


def test_option_keys_are_stable_slugs():
    assert slug("Precios y cuotas") == "precios_y_cuotas"
    assert slug("Inscripción") == "inscripcion"


def test_questions_are_checked():
    questions = clean(defaults())
    assert [q["key"] for q in questions] == ["intent", "sentiment", "urgency", "team"]
    with pytest.raises(ValueError, match="option_count"):
        clean([{"key": "intent", "instructions": "¿Qué quiere?", "options": [{"description": "Una sola"}]}])
    with pytest.raises(ValueError, match="duplicate_option"):
        clean(
            [
                {
                    "key": "intent",
                    "instructions": "¿Qué quiere?",
                    "options": [{"description": "Precios"}, {"description": "precios"}],
                }
            ]
        )
    with pytest.raises(ValueError, match="instructions"):
        clean([{"key": "x", "instructions": " ", "options": []}])


def test_the_team_question_needs_teams():
    questions = clean(defaults())
    asked = as_service_questions(questions)
    assert "team" not in asked  # no teams, no question
    assert asked["intent"]["type"] == "choice"
    assert asked["intent"]["criteria"]["precios"].startswith("Pregunta precios")
    for q in questions:
        if q["key"] == "team":
            q["options"] = team_options([(3, "Ventas", "Inscripciones y precios"), (4, "Secretaría", None)])
    asked = as_service_questions(questions)
    assert asked["team"]["criteria"] == {
        "team_3": "Ventas: Inscripciones y precios",
        "team_4": "Secretaría",
        "ninguno": "Ningún equipo en particular",
    }


def test_the_services_answer_is_read():
    decisions = parse(
        {
            "model": "jev-1.14.0",
            "answers": {
                "intent": {
                    "type": "choice",
                    "choice": "precios",
                    "confidence": 0.91,
                    "probabilities": {"precios": 0.95, "otro": 0.05},
                },
                "broken": {"type": "choice"},
            },
            "usage": {"input_tokens": 420, "output_tokens": 30},
        }
    )
    assert decisions.model == "jev-1.14.0"
    assert list(decisions.answers) == ["intent"]
    assert decisions.answers["intent"].choice == "precios"
    assert decisions.answers["intent"].confidence == 0.91
    assert decisions.input_tokens == 420


def test_speaker_labels_survive_a_user_called_cliente():
    from types import SimpleNamespace

    from app.domains.conversations.models import MESSAGE_TYPE_INCOMING, MESSAGE_TYPE_OUTGOING
    from app.domains.decisions.service import _transcript

    messages = [
        SimpleNamespace(message_type=MESSAGE_TYPE_INCOMING, content="Hola, soy Ana. ¿Precio?"),
        SimpleNamespace(message_type=MESSAGE_TYPE_OUTGOING, content="Hola Ana, te paso el precio"),
    ]
    text = _transcript(messages, ["Cliente Demo", "Ana"])  # type: ignore[arg-type]
    assert text.splitlines() == ["Cliente: Hola, soy [nombre]. ¿Precio?", "Agente: Hola [nombre], te paso el precio"]


def test_the_local_model_reads_the_urgency_from_the_most_urgent():
    criteria = {"baja": "b", "otra": "o", "media": "m", "urgente": "u", "nada": "n", "alta": "a"}
    listed = [k for k, _ in local._listed("urgency", criteria)]
    # Those that set no priority after them, in their order.
    assert listed == ["urgente", "alta", "media", "baja", "otra", "nada"]
    assert [k for k, _ in local._listed("intent", criteria)] == list(criteria)


def test_the_local_reason_ends_at_a_whole_word():
    assert local._reason(None) == ""
    assert local._reason("  Quiere   anotarse ") == "Quiere anotarse"
    words = "Quiere anotarse el año que viene y pregunta por cupos " * 3
    # Stopped at the limit in the middle of a word, with a stray character.
    cut = words[: local.REASON_MAX - 1] + "亟"
    assert local._reason(cut) == words[: local.REASON_MAX - 1].rsplit(" ", 1)[0] + "…"
    # A doubled space does not hide that it was stopped.
    spaced = local._reason(("Quiere  anotarse " + words)[: local.REASON_MAX - 1] + "亟")
    assert spaced.endswith("…") and "亟" not in spaced
    # With no space to cut at.
    assert local._reason("報" * local.REASON_MAX) == "報" * (local.REASON_MAX - 1) + "…"


def test_a_phone_the_cut_would_shorten_still_comes_out():
    tail = " al 099 123 45"
    reason = ("Pide que lo llamen por la inscripción " * 4)[: local.REASON_MAX - len(tail)] + tail
    assert len(reason) == local.REASON_MAX
    out = local._reason(reason)
    assert "099" not in out and "123" not in out and out.endswith("…")
