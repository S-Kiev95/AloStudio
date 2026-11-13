"""Highlights are offsets into the *original* text, accents intact.

The search matches on folded text ("envio" finds "Envío"), so the offsets
have to be mapped back — otherwise a highlight lands one letter off for
every accent before it, or on the wrong word entirely.
"""

from __future__ import annotations

from app.domains.conversations.message_search import _terms, make_snippet


def _marked(snippet: str, highlights: list[list[int]]) -> list[str]:
    return [snippet[a:b] for a, b in highlights]


def test_an_unaccented_query_highlights_the_accented_word():
    snippet, hl = make_snippet("Le hicimos el Envío ayer", _terms("envio"))
    assert _marked(snippet, hl) == ["Envío"]


def test_offsets_survive_accents_before_the_match():
    text = "Árbol, canción, información: después mandá la factura"
    snippet, hl = make_snippet(text, _terms("factura"))
    assert _marked(snippet, hl) == ["factura"]


def test_every_occurrence_and_every_word_is_marked():
    snippet, hl = make_snippet("pago en cuotas; la cuota dos", _terms("cuota pago"))
    assert _marked(snippet, hl) == ["pago", "cuota", "cuota"]


def test_a_long_message_is_cut_around_the_match():
    text = "relleno " * 60 + "el número de seguimiento es AB123" + " fin" * 80
    snippet, hl = make_snippet(text, _terms("seguimiento"))
    assert snippet.startswith("…") and snippet.endswith("…")
    assert _marked(snippet, hl) == ["seguimiento"]
    assert len(snippet) <= 230


def test_operators_of_the_query_are_not_highlighted():
    assert _terms('"pago total" -cuotas or envio') == ["pago", "total", "envio"]


def test_no_literal_match_opens_at_the_start():
    # A stemmed or typo match: found by the database, nothing to mark here.
    snippet, hl = make_snippet("pagamos en tres cuotas", _terms("cuotsa"))
    assert snippet == "pagamos en tres cuotas" and hl == []
