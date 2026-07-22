"""Unit tests for the WhatsApp template presenter (no DB).

The composer needs each approved template's body text and the distinct
``{{n}}`` positions it must collect values for.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.domains.whatsapp.templates_router import (
    _approved,
    _body_text,
    _present,
)


def _tpl(**over):
    base = {
        "name": "order_update",
        "language": "es_AR",
        "status": "APPROVED",
        "category": "UTILITY",
        "components": [
            {"type": "HEADER", "text": "Header {{1}}"},
            {"type": "BODY", "text": "Hola {{1}}, tu pedido {{2}} — total {{2}}"},
            {"type": "BUTTONS", "buttons": []},
        ],
    }
    base.update(over)
    return base


def test_body_text_reads_the_body_component_only():
    # Not the header, even though it also has {{1}}.
    assert _body_text(_tpl()) == "Hola {{1}}, tu pedido {{2}} — total {{2}}"


def test_present_dedupes_and_sorts_variables():
    out = _present(_tpl())
    assert out["name"] == "order_update"
    assert out["language"] == "es_AR"
    # {{1}}, {{2}}, {{2}} → distinct, sorted
    assert out["variables"] == [1, 2]


def test_present_no_variables_when_body_is_static():
    out = _present(_tpl(components=[{"type": "BODY", "text": "Gracias."}]))
    assert out["variables"] == []
    assert out["body_text"] == "Gracias."


def test_present_handles_missing_body():
    out = _present(_tpl(components=[{"type": "HEADER", "text": "hi"}]))
    assert out["body_text"] is None
    assert out["variables"] == []


def test_approved_filters_out_non_approved():
    channel = SimpleNamespace(
        message_templates=[
            _tpl(name="a", status="APPROVED"),
            _tpl(name="b", status="PENDING"),
            _tpl(name="c", status="REJECTED"),
            "not-a-dict",
        ]
    )
    names = [t["name"] for t in _approved(channel)]
    assert names == ["a"]
