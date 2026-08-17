"""What an outgoing reply looks like when it lands.

The signature is typed by a person into a textarea, so the sharp edge here
is treating it as markup: a stray "<" would swallow the rest of it, and a
pasted tag would reach every customer's inbox.
"""

from __future__ import annotations

import pytest

from app.domains.email.template import render_html, render_plain

pytestmark = pytest.mark.unit

SIGNATURE = "Instituto Ejemplo\nAtención: 9 a 17 h\ninfo@ejemplo.edu.uy"
LOGO = "https://cdn.ejemplo.edu.uy/logo.png"


class TestPlainPart:
    def test_carries_the_message(self):
        assert "Ahí va el detalle" in render_plain(body="Ahí va el detalle")

    def test_separates_the_signature_the_way_mail_readers_expect(self):
        out = render_plain(body="Hola", signature=SIGNATURE)
        # "-- " is the sig delimiter every mail reader knows; it is what
        # lets a client collapse the signature instead of quoting it back.
        assert "\n\n-- \n" in out
        assert out.endswith(SIGNATURE)

    def test_a_mailbox_with_no_signature_sends_what_it_always_sent(self):
        assert render_plain(body="Hola", signature="") == "Hola"

    def test_is_readable_prose_not_stripped_html(self):
        out = render_plain(body="Hola", signature=SIGNATURE)
        assert "<" not in out


class TestHtmlPart:
    def test_carries_the_message(self):
        assert "Ahí va el detalle" in render_html(body="Ahí va el detalle")

    def test_keeps_the_line_breaks_the_writer_typed(self):
        # Someone pressing Enter expects a line break; HTML collapses it.
        out = render_html(body="Primera\nSegunda")
        assert "Primera<br>Segunda" in out

    def test_starts_a_new_paragraph_on_a_blank_line(self):
        out = render_html(body="Uno\n\nDos")
        assert out.count("<p ") == 2

    def test_shows_the_logo(self):
        assert f'src="{LOGO}"' in render_html(body="Hola", logo_url=LOGO)

    def test_gives_the_logo_no_alt_text(self):
        # A blocked image should leave a gap, not the word "logo" — the
        # signature underneath already names the sender.
        assert 'alt=""' in render_html(body="Hola", logo_url=LOGO)

    def test_shows_the_signature(self):
        out = render_html(body="Hola", signature=SIGNATURE)
        assert "Instituto Ejemplo" in out
        assert "Instituto Ejemplo<br>Atención: 9 a 17 h" in out

    def test_draws_no_divider_when_there_is_nothing_below_it(self):
        assert "<hr" not in render_html(body="Hola")

    def test_draws_a_divider_once_there_is(self):
        assert "<hr" in render_html(body="Hola", signature=SIGNATURE)


class TestEscaping:
    def test_a_signature_is_text_not_markup(self):
        out = render_html(body="Hola", signature="Ventas <ventas@x.com>")
        assert "&lt;ventas@x.com&gt;" in out
        # Unescaped, the angle brackets would eat the rest of the line.
        assert "<ventas@x.com>" not in out

    def test_a_pasted_tag_cannot_reach_the_recipient(self):
        out = render_html(
            body="Hola", signature="<script>alert(1)</script>"
        )
        assert "<script>" not in out
        assert "&lt;script&gt;" in out

    def test_the_message_body_is_escaped_too(self):
        out = render_html(body="Comparar 3 < 5 & 6 > 2")
        assert "3 &lt; 5 &amp; 6 &gt; 2" in out

    def test_a_logo_url_cannot_break_out_of_the_attribute(self):
        out = render_html(body="Hola", logo_url='x" onerror="alert(1)')
        assert 'onerror="alert(1)"' not in out
        assert "&quot;" in out


class TestBothParts:
    @pytest.mark.parametrize(
        "render", [render_plain, render_html], ids=["plain", "html"]
    )
    def test_an_unconfigured_mailbox_still_sends_the_message(self, render):
        assert "Ahí va" in render(body="Ahí va")

    def test_the_styling_is_inline_because_clients_drop_style_blocks(self):
        out = render_html(body="Hola", signature=SIGNATURE, logo_url=LOGO)
        assert "<style" not in out
        assert 'style="' in out
