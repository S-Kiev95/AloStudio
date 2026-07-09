"""Unit tests for the WhatsApp template-params processor.

Pure (no DB) — ``process_template_params`` turns a stored ``template_params``
blob + the channel's synced ``message_templates`` into the ``template_info``
that ``send_template_message`` consumes.
"""

from __future__ import annotations

from app.domains.whatsapp.template_processor import process_template_params

_APPROVED = [
    {"name": "hello_world", "language": "en_US", "status": "APPROVED"},
    {"name": "order_update", "language": "es_AR", "status": "APPROVED"},
    {"name": "old_one", "language": "en_US", "status": "REJECTED"},
]


def test_no_params_template_resolves_with_empty_components():
    info = process_template_params(
        {"name": "hello_world", "language": "en_US"}, _APPROVED
    )
    assert info == {
        "name": "hello_world",
        "lang_code": "en_US",
        "parameters": [],
    }


def test_body_params_become_ordered_body_component():
    info = process_template_params(
        {
            "name": "order_update",
            "language": "es_AR",
            # deliberately out of order to prove numeric sort
            "processed_params": {"body": {"2": "#123", "1": "Ana"}},
        },
        _APPROVED,
    )
    assert info is not None
    assert info["name"] == "order_update"
    assert info["lang_code"] == "es_AR"
    assert info["parameters"] == [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": "Ana"},
                {"type": "text", "text": "#123"},
            ],
        }
    ]


def test_lang_code_alias_and_case_insensitive_match():
    # ``lang_code`` alias + language casing shouldn't matter.
    info = process_template_params(
        {"name": "hello_world", "lang_code": "EN_us"}, _APPROVED
    )
    assert info is not None and info["name"] == "hello_world"


def test_unknown_or_unapproved_template_returns_none():
    assert process_template_params(
        {"name": "does_not_exist", "language": "en_US"}, _APPROVED
    ) is None
    # present but REJECTED → not sendable.
    assert process_template_params(
        {"name": "old_one", "language": "en_US"}, _APPROVED
    ) is None


def test_blank_or_nameless_input_returns_none():
    assert process_template_params(None, _APPROVED) is None
    assert process_template_params({}, _APPROVED) is None
    assert process_template_params({"language": "en_US"}, _APPROVED) is None


def test_blank_body_values_are_dropped():
    info = process_template_params(
        {
            "name": "order_update",
            "language": "es_AR",
            "processed_params": {"body": {"1": "  ", "2": ""}},
        },
        _APPROVED,
    )
    # All values blank → no body component at all.
    assert info == {
        "name": "order_update",
        "lang_code": "es_AR",
        "parameters": [],
    }
