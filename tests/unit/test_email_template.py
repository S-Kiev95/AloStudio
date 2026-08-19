"""What an outgoing reply looks like when it lands.

The signature is typed by a person into a textarea, so the sharp edge here
is treating it as markup: a stray "<" would swallow the rest of it, and a
pasted tag would reach every customer's inbox.
"""

from __future__ import annotations

import pytest

from app.domains.email.template import (
    TemplateError,
    render_html,
    render_plain,
    render_template,
    validate_template,
)

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


class TestMailboxTemplate:
    TEMPLATE = (
        '<div style="background:#003366;padding:20px">'
        "{{logo}}<h1>Instituto Ejemplo</h1></div>"
        "<div>{{contenido}}</div><footer>{{firma}}</footer>"
    )

    def test_no_template_keeps_the_built_in_layout(self):
        """Customising is opt-in; an untouched mailbox sends what it sent."""
        out = render_template(template="", body="Hola", signature=SIGNATURE)
        assert out == render_html(body="Hola", signature=SIGNATURE)

    def test_the_authors_markup_survives(self):
        out = render_template(template=self.TEMPLATE, body="Hola")
        assert '<div style="background:#003366;padding:20px">' in out
        assert "<h1>Instituto Ejemplo</h1>" in out

    def test_the_message_lands_where_the_author_put_it(self):
        out = render_template(template=self.TEMPLATE, body="Ahí va")
        assert "<div><p" in out
        assert "Ahí va" in out

    def test_the_signature_and_logo_fill_their_places(self):
        out = render_template(
            template=self.TEMPLATE,
            body="Hola",
            signature=SIGNATURE,
            logo_url=LOGO,
        )
        assert f'src="{LOGO}"' in out
        assert "Instituto Ejemplo<br>Atención: 9 a 17 h" in out

    def test_an_unused_placeholder_leaves_nothing_behind(self):
        # An empty signature must not print the literal "{{firma}}".
        out = render_template(template=self.TEMPLATE, body="Hola")
        assert "{{firma}}" not in out
        assert "{{logo}}" not in out
        assert "{{contenido}}" not in out

    def test_what_is_substituted_in_is_still_escaped(self):
        """The author owns the layout; the agent's text is not markup."""
        out = render_template(
            template=self.TEMPLATE,
            body="<script>alert(1)</script>",
            signature="Ventas <ventas@x.com>",
        )
        assert "<script>" not in out
        assert "&lt;script&gt;" in out
        assert "&lt;ventas@x.com&gt;" in out


class TestTemplateValidation:
    def test_a_template_without_the_message_is_refused(self):
        # It would send successfully with the reply missing, and nobody
        # would find out until a customer said so.
        with pytest.raises(TemplateError):
            validate_template("<div>Solo el encabezado</div>")

    def test_a_template_with_the_message_is_accepted(self):
        validate_template("<div>{{contenido}}</div>")

    def test_an_empty_template_is_accepted(self):
        """Empty means the built-in layout, not a broken template."""
        validate_template("")
        validate_template("   ")

    def test_the_error_says_what_to_add(self):
        with pytest.raises(TemplateError, match=r"\{\{contenido\}\}"):
            validate_template("<div>nada</div>")


class TestAgentSignature:
    """Who wrote the reply, as opposed to which institution it came from.

    A reply usually wants both: the person signs off, the mailbox carries
    the letterhead. They are not alternatives.
    """

    AGENT = "Ana Rodríguez\nAtención al cliente"

    def test_the_writer_signs_above_the_letterhead(self):
        out = render_plain(
            body="Ahí va", signature=SIGNATURE, agent_signature=self.AGENT
        )
        # "-- " is what a mail reader may collapse as boilerplate, so the
        # person's name has to sit above it, with the message.
        assert out.index("Ana Rodríguez") < out.index("-- ")
        assert out.endswith(SIGNATURE)

    def test_html_shows_both(self):
        out = render_html(
            body="Ahí va", signature=SIGNATURE, agent_signature=self.AGENT
        )
        assert "Ana Rodríguez<br>Atención al cliente" in out
        assert "Instituto Ejemplo" in out

    def test_an_agent_with_no_signature_changes_nothing(self):
        assert render_html(body="Hola", signature=SIGNATURE) == render_html(
            body="Hola", signature=SIGNATURE, agent_signature=""
        )

    def test_it_works_with_no_mailbox_signature_at_all(self):
        out = render_plain(body="Hola", agent_signature=self.AGENT)
        assert out == "Hola\n\nAna Rodríguez\nAtención al cliente"

    def test_it_is_escaped_like_every_other_typed_field(self):
        out = render_html(body="Hola", agent_signature="Ana <ana@x.com>")
        assert "&lt;ana@x.com&gt;" in out
        assert "<ana@x.com>" not in out

    def test_a_template_can_place_it(self):
        out = render_template(
            template="<div>{{contenido}}</div><i>{{firma_agente}}</i>",
            body="Hola",
            agent_signature=self.AGENT,
        )
        assert "<i>Ana Rodríguez<br>Atención al cliente</i>" in out

    def test_a_template_that_omits_it_simply_never_shows_who_answered(self):
        out = render_template(
            template="<div>{{contenido}}</div>",
            body="Hola",
            agent_signature=self.AGENT,
        )
        assert "Ana" not in out
        assert "{{firma_agente}}" not in out
