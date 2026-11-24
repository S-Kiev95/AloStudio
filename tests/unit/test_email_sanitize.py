"""Security tests for server-side email HTML sanitization.

Every dangerous construct named in Section 5 of the plan must be stripped
cleanly while legitimate inline-styled email tables, links, images and
template placeholders survive intact.
"""

from __future__ import annotations

import pytest

from app.domains.email.sanitize import sanitize_email_html

pytestmark = pytest.mark.unit


class TestDangerousMarkupRemoved:
    def test_strips_script_tags_and_body(self):
        dirty = '<p>Hola</p><script>alert("xss")</script>{{contenido}}'
        clean = sanitize_email_html(dirty)
        assert "<script" not in clean.lower()
        assert "alert(" not in clean
        assert "<p>Hola</p>" in clean
        assert "{{contenido}}" in clean

    def test_strips_iframe_object_embed_and_form(self):
        dirty = (
            "<div>{{contenido}}</div>"
            '<iframe src="https://evil.example/frame"></iframe>'
            '<object data="https://evil.example/app.swf"></object>'
            '<embed src="https://evil.example/x.swf">'
            '<form action="https://evil.example/steal">'
            '<input type="password" name="pw"><button>Robar</button></form>'
        )
        clean = sanitize_email_html(dirty)
        for forbidden in ("<iframe", "<object", "<embed", "<form", "<input", "<button"):
            assert forbidden not in clean.lower()
        assert "{{contenido}}" in clean

    def test_strips_inline_event_handlers(self):
        dirty = (
            '<div onclick="alert(1)" onmouseover="steal()">'
            '<img src="https://cdn.example/logo.png" onerror="alert(2)" onload="alert(3)">'
            '<a href="https://example.com" onfocus="alert(4)">Ver</a>'
            "{{contenido}}</div>"
        )
        clean = sanitize_email_html(dirty)
        for handler in ("onclick", "onmouseover", "onerror", "onload", "onfocus"):
            assert handler not in clean.lower()
        assert 'src="https://cdn.example/logo.png"' in clean
        assert 'href="https://example.com"' in clean

    def test_strips_javascript_and_vbscript_urls(self):
        dirty = (
            '<a href="javascript:alert(1)">Click</a>'
            '<a href="  JaVaScRiPt:alert(2)">Click2</a>'
            '<a href="vbscript:msgbox(1)">Click3</a>'
            '<img src="javascript:alert(3)" alt="x">'
            "{{contenido}}"
        )
        clean = sanitize_email_html(dirty)
        assert "javascript:" not in clean.lower()
        assert "vbscript:" not in clean.lower()

    def test_strips_non_image_and_svg_data_urls(self):
        dirty = (
            '<a href="data:text/html,<script>alert(1)</script>">Bad link</a>'
            '<img src="data:image/svg+xml;base64,PHN2ZyBvbmxvYWQ9YWxlcnQoMSk+PC9zdmc+" alt="svg">'
            '<img src="data:text/html;base64,PHNjcmlwdD4=" alt="html">'
            "{{contenido}}"
        )
        clean = sanitize_email_html(dirty)
        assert "data:text/html" not in clean.lower()
        assert "data:image/svg+xml" not in clean.lower()

    def test_strips_style_blocks_and_dangerous_css(self):
        dirty = (
            "<style>body { background: url(javascript:alert(1)); }</style>"
            '<div style="color:#111;width:expression(alert(1));background:url(javascript:alert(2));position:fixed">'
            "{{contenido}}</div>"
        )
        clean = sanitize_email_html(dirty)
        assert "<style" not in clean.lower()
        assert "expression" not in clean.lower()
        assert "javascript:" not in clean.lower()
        assert "position:fixed" not in clean.lower()
        assert "color:#111" in clean


class TestValidEmailMarkupPreserved:
    def test_preserves_inline_table_layout_and_placeholders(self):
        good = (
            '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
            'style="width:600px;margin:0 auto;background:#ffffff">'
            '<tr><td style="padding:24px;color:#1f2328;font-size:15px">'
            "{{logo}}{{contenido}}{{firma}}{{firma_organizacion}}"
            "</td></tr></table>"
        )
        clean = sanitize_email_html(good)
        assert "<table" in clean
        assert 'width="600"' in clean
        assert "background:#ffffff" in clean
        assert "{{contenido}}" in clean
        assert "{{firma}}" in clean
        assert "{{firma_organizacion}}" in clean
        assert "{{logo}}" in clean

    def test_allows_https_and_raster_data_images(self):
        good = (
            '<img src="https://cdn.example.com/logo.png" width="160" alt="Logo">'
            '<img src="data:image/png;base64,iVBORw0KGgo=" alt="Inline">'
        )
        clean = sanitize_email_html(good)
        assert 'src="https://cdn.example.com/logo.png"' in clean
        assert 'src="data:image/png;base64,iVBORw0KGgo="' in clean

    def test_allows_mailto_and_tel_links(self):
        good = '<a href="mailto:hola@ejemplo.com">Escribir</a><a href="tel:+59899123456">Llamar</a>'
        clean = sanitize_email_html(good)
        assert 'href="mailto:hola@ejemplo.com"' in clean
        assert 'href="tel:+59899123456"' in clean

    def test_preserves_body_background_from_imported_full_document(self):
        imported = (
            "<!DOCTYPE html><html><head><title>Promo</title><style>p{color:red}</style></head>"
            '<body style="background:#f4f5f7;padding:24px"><p>{{contenido}}</p></body></html>'
        )
        clean = sanitize_email_html(imported)
        assert "<style" not in clean.lower()
        assert "<title" not in clean.lower()
        assert "background:#f4f5f7" in clean
        assert "{{contenido}}" in clean

    def test_empty_input_returns_empty_string(self):
        assert sanitize_email_html("") == ""
        assert sanitize_email_html("   ") == ""
        assert sanitize_email_html(None) == ""
