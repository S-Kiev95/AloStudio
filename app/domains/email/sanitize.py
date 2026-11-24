"""Server-side HTML sanitization for email templates and signatures.

Every piece of authored or AI-generated markup passes through
:func:`sanitize_email_html` before it is persisted or returned to the
editor. We use ``nh3`` (Rust's html5ever / ammonia sanitizer) so parser
quirks and mutation-XSS tricks cannot sneak past regexes.

Policy (Section 5 of the email templates plan):
  * Allow layout and typography tags that email clients understand
    (tables, divs, spans, headings, paragraphs, links, images, lists).
  * Strip dangerous tags **and** their contents: ``<script>``, ``<iframe>``,
    ``<object>``, ``<embed>``, ``<form>``, ``<style>``, ``<svg>``, etc.
  * Strip every ``on*`` event handler attribute (only an explicit
    allowlist of attributes survives).
  * Reject ``javascript:``, ``vbscript:`` and ``data:`` URLs, **except**
    raster ``data:image/(png|jpeg|jpg|gif|webp);base64,...`` on ``<img>``
    (never ``data:image/svg+xml`` or ``data:`` on links).
  * Strip dangerous CSS constructs inside inline ``style`` attributes
    (``expression()``, ``javascript:``, ``url(data:...)``, ``@import``,
    ``behavior:``, ``-moz-binding``).
"""

from __future__ import annotations

import re

import nh3

_ALLOWED_TAGS: set[str] = {
    "a",
    "article",
    "b",
    "blockquote",
    "br",
    "caption",
    "center",
    "code",
    "col",
    "colgroup",
    "dd",
    "del",
    "div",
    "dl",
    "dt",
    "em",
    "figcaption",
    "figure",
    "font",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "i",
    "img",
    "ins",
    "li",
    "main",
    "mark",
    "ol",
    "p",
    "pre",
    "s",
    "section",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}

_CLEAN_CONTENT_TAGS: set[str] = {
    "applet",
    "base",
    "button",
    "embed",
    "form",
    "iframe",
    "input",
    "link",
    "math",
    "meta",
    "noscript",
    "object",
    "option",
    "script",
    "select",
    "style",
    "svg",
    "template",
    "textarea",
    "title",
}

_COMMON_ATTRS: set[str] = {"align", "class", "dir", "lang", "role", "style", "title"}

_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "*": _COMMON_ATTRS,
    "a": {"href", "name", "target"},
    "col": {"span", "width"},
    "colgroup": {"span", "width"},
    "font": {"color", "face", "size"},
    "img": {"alt", "border", "height", "src", "width"},
    "table": {
        "bgcolor",
        "border",
        "cellpadding",
        "cellspacing",
        "height",
        "width",
    },
    "tbody": {"bgcolor", "valign"},
    "td": {"bgcolor", "colspan", "height", "nowrap", "rowspan", "valign", "width"},
    "tfoot": {"bgcolor", "valign"},
    "th": {"bgcolor", "colspan", "height", "nowrap", "rowspan", "scope", "valign", "width"},
    "thead": {"bgcolor", "valign"},
    "tr": {"bgcolor", "height", "valign"},
}

# Placeholder tokens allowed verbatim as href/src before variable substitution.
_PLACEHOLDER_RE = re.compile(r"^\{\{[a-z_]+\}\}$")

# Only safe raster image data URLs are allowed on <img src="...">.
# SVG is explicitly excluded because SVG can embed <script> and event handlers.
_SAFE_IMG_DATA_RE = re.compile(
    r"^data:image/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=\s]+$",
    re.IGNORECASE,
)

# Relative paths pointing to our own public asset proxy (e.g. during local dev).
_SAFE_URL_RE = re.compile(r"^(?:https?://|mailto:|tel:|#|/)", re.IGNORECASE)

# Inline style guard: remove dangerous CSS declarations while keeping safe
# email presentation properties (color, background, padding, font-*, border, etc.).
_DANGEROUS_CSS_RE = re.compile(
    r"(?:"
    r"expression\s*\("
    r"|javascript\s*:"
    r"|vbscript\s*:"
    r"|behavior\s*:"
    r"|-moz-binding\s*:"
    r"|@import"
    r"|url\s*\(\s*['\"]?\s*(?!https?://)"
    r")",
    re.IGNORECASE,
)

# Preserve inline styles on a pasted <body> by turning it into a <div> before
# html5ever's fragment parser discards the <body> wrapper.
_BODY_OPEN_WITH_STYLE_RE = re.compile(r"<body\b([^>]*\bstyle\s*=[^>]*)>", re.IGNORECASE)
_BODY_CLOSE_RE = re.compile(r"</body\s*>", re.IGNORECASE)


def _clean_style(value: str) -> str | None:
    """Keep safe inline CSS declarations; drop any declaration with a dangerous value."""
    # Strip CSS comments first so `exp/* */ression(` cannot sneak through.
    no_comments = re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL)
    kept: list[str] = []
    for raw_decl in no_comments.split(";"):
        decl = raw_decl.strip()
        if not decl or ":" not in decl:
            continue
        prop, val = decl.split(":", 1)
        prop_clean = prop.strip().lower()
        val_clean = val.strip()
        if not prop_clean or not val_clean:
            continue
        if prop_clean in {"behavior", "-moz-binding"}:
            continue
        # Disallow fixed positioning that could overlay the preview / client UI.
        if prop_clean == "position" and val_clean.lower() in {"fixed", "sticky"}:
            continue
        if _DANGEROUS_CSS_RE.search(decl):
            continue
        kept.append(f"{prop.strip()}:{val_clean}")
    return ";".join(kept) if kept else None


def _attribute_filter(tag: str, attr: str, value: str) -> str | None:
    val = value.strip()
    if attr == "style":
        return _clean_style(val)

    if attr == "target":
        return val if val in {"_blank", "_self"} else None

    if tag == "img" and attr == "src":
        if _PLACEHOLDER_RE.match(val):
            return val
        if _SAFE_IMG_DATA_RE.match(val):
            return val
        if re.match(r"^https?://", val, re.IGNORECASE) or val.startswith("/public/"):
            return val
        return None

    if tag == "a" and attr == "href":
        if _PLACEHOLDER_RE.match(val):
            return val
        if _SAFE_URL_RE.match(val):
            return val
        return None

    return value


def sanitize_email_html(html: str | None) -> str:
    """Return email-safe, XSS-free HTML.

    Empty / whitespace-only input returns ``""``.
    """
    raw = str(html or "")
    if not raw.strip():
        return ""

    # If the user imported a full HTML file whose <body> carries inline styles
    # (e.g. page background color), promote that <body> into a <div> so the
    # styles survive html5ever fragment cleaning.
    if _BODY_OPEN_WITH_STYLE_RE.search(raw):
        raw = _BODY_OPEN_WITH_STYLE_RE.sub(r"<div\1>", raw, count=1)
        raw = _BODY_CLOSE_RE.sub("</div>", raw, count=1)

    cleaned = nh3.clean(
        raw,
        tags=_ALLOWED_TAGS,
        clean_content_tags=_CLEAN_CONTENT_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto", "tel", "data"},
        attribute_filter=_attribute_filter,
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
    return cleaned.strip()


__all__ = ["sanitize_email_html"]
