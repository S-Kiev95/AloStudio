"""The shape an outgoing reply arrives in.

Replies used to go out as bare plain text: no signature, no logo, nothing
saying which institution was writing. This builds both parts of a
multipart/alternative — the text one for clients that ask for it and the
HTML one for the rest — from the mailbox's own branding.

Two rules drive the whole module.

**The signature is written by a person, not authored as markup.** It is
typed into a textarea by whoever runs the desk, so it is escaped and its
line breaks converted. Treating it as HTML would let a stray ``<`` swallow
the rest of the signature, and a pasted tag reach every customer's inbox.

**The HTML has to survive a mail client.** Gmail and Outlook strip
``<style>`` blocks, external stylesheets, and most of what a browser
accepts, so every rule here is an inline attribute on the element it
applies to. That is why this looks like 2004 and not like the rest of the
frontend — it is the format that renders.
"""

from __future__ import annotations

from html import escape

# Inlined rather than a stylesheet: mail clients drop <style> blocks.
_BODY = (
    "margin:0;padding:24px;background:#f4f5f7;"
    "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
)
_CARD = (
    "max-width:560px;margin:0 auto;background:#ffffff;border-radius:8px;"
    "padding:24px;color:#1f2328;font-size:15px;line-height:1.5;"
)
_RULE = "border:none;border-top:1px solid #e5e7eb;margin:20px 0 16px;"
_SIGNATURE = "color:#5b6470;font-size:13px;line-height:1.45;"
_LOGO = "max-width:160px;max-height:56px;margin-bottom:12px;display:block;"


def _paragraphs(text: str) -> str:
    """Escaped body, blank-line separated, single newlines kept as breaks.

    Someone writing a reply presses Enter and expects a line break; HTML
    would otherwise collapse it into a space.
    """
    blocks = [b for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(
        f'<p style="margin:0 0 12px;">{escape(b).replace(chr(10), "<br>")}</p>'
        for b in blocks
    )


def render_plain(*, body: str, signature: str = "") -> str:
    """The text/plain part.

    Kept as the real alternative and not a stripped afterthought: a client
    that prefers text should get something a person can read, with the
    signature separated by the ``-- `` convention mail readers know.
    """
    body = (body or "").strip()
    signature = (signature or "").strip()
    if not signature:
        return body
    return f"{body}\n\n-- \n{signature}"


def render_html(
    *, body: str, signature: str = "", logo_url: str = ""
) -> str:
    """The text/html part: the message, then the mailbox's sign-off."""
    parts = [
        f'<body style="{_BODY}">',
        f'<div style="{_CARD}">',
        _paragraphs((body or "").strip()),
    ]

    signature = (signature or "").strip()
    logo_url = (logo_url or "").strip()
    if signature or logo_url:
        parts.append(f'<hr style="{_RULE}">')
        if logo_url:
            # alt is empty on purpose: the signature below already names
            # the sender, and a blocked image should leave a gap, not the
            # word "logo".
            parts.append(
                f'<img src="{escape(logo_url, quote=True)}" alt="" '
                f'style="{_LOGO}">'
            )
        if signature:
            parts.append(
                f'<div style="{_SIGNATURE}">'
                f'{escape(signature).replace(chr(10), "<br>")}'
                f"</div>"
            )

    parts.append("</div></body>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Mailbox-authored templates
# ---------------------------------------------------------------------------
# What an author can drop into their own HTML. Substituted with *escaped*
# values, so the author owns the layout while the agent's reply and the
# mailbox's signature cannot inject markup into it.
PLACEHOLDER_CONTENT = "{{contenido}}"
PLACEHOLDER_SIGNATURE = "{{firma}}"
PLACEHOLDER_LOGO = "{{logo}}"

PLACEHOLDERS = (PLACEHOLDER_CONTENT, PLACEHOLDER_SIGNATURE, PLACEHOLDER_LOGO)


class TemplateError(ValueError):
    """A template that would send a broken email."""


def validate_template(template: str) -> None:
    """Refuse a template that would drop the message.

    The one rule worth enforcing: without ``{{contenido}}`` every reply
    goes out with the agent's text missing, and nothing downstream would
    notice — the send succeeds and the customer receives an empty shell.
    """
    if not template.strip():
        return
    if PLACEHOLDER_CONTENT not in template:
        raise TemplateError(
            f"La plantilla tiene que incluir {PLACEHOLDER_CONTENT}, "
            "que es donde va el mensaje."
        )


def render_template(
    *, template: str, body: str, signature: str = "", logo_url: str = ""
) -> str:
    """Fill a mailbox's own HTML.

    Falls back to :func:`render_html` when there is no template, so the
    built-in layout stays the default rather than something to opt into.
    """
    if not template.strip():
        return render_html(body=body, signature=signature, logo_url=logo_url)

    signature = (signature or "").strip()
    logo_url = (logo_url or "").strip()
    logo_tag = (
        f'<img src="{escape(logo_url, quote=True)}" alt="" style="{_LOGO}">'
        if logo_url
        else ""
    )
    return (
        template.replace(PLACEHOLDER_CONTENT, _paragraphs((body or "").strip()))
        .replace(
            PLACEHOLDER_SIGNATURE,
            escape(signature).replace(chr(10), "<br>") if signature else "",
        )
        .replace(PLACEHOLDER_LOGO, logo_tag)
    )


__all__ = [
    "PLACEHOLDERS",
    "PLACEHOLDER_CONTENT",
    "PLACEHOLDER_LOGO",
    "PLACEHOLDER_SIGNATURE",
    "TemplateError",
    "render_html",
    "render_plain",
    "render_template",
    "validate_template",
]
