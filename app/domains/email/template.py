"""The shape an outgoing reply arrives in.

Replies used to go out as bare plain text: no signature, no logo, nothing
saying which institution was writing. This builds both parts of a
multipart/alternative — the text one for clients that ask for it and the
HTML one for the rest — from the chosen template and the resolved signatures.

Two rules drive the whole module.

**Plain-text signatures are written by a person, not authored as markup.**
``users.message_signature`` and ``channel_email.signature`` are typed into a
textarea, so they are escaped and their line breaks converted. Treating plain
text as HTML would let a stray ``<`` swallow the rest of the signature, and a
pasted tag reach every customer's inbox. Rich HTML signatures stored in
``email_signatures`` are sanitized on save and interpolated with escaped user
profile variables.

**The HTML has to survive a mail client.** Gmail and Outlook strip
``<style>`` blocks, external stylesheets, and most of what a browser
accepts, so every rule here is an inline attribute on the element it
applies to.
"""

from __future__ import annotations

import re
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
# The agent's own sign-off sits with the message, not down in the
# institutional block — it is the person writing, not the letterhead.
_AGENT = "color:#1f2328;font-size:14px;line-height:1.45;margin-top:16px;"
_LOGO = "max-width:160px;max-height:56px;margin-bottom:12px;display:block;"
_APPENDED_SIG = "margin-top:20px;padding-top:16px;border-top:1px solid #e5e7eb;"
_AVATAR = "width:48px;height:48px;border-radius:50%;object-fit:cover;display:block;border:0;"

_SAFE_PHOTO_URL_RE = re.compile(r"^(?:https?://|/public/)", re.IGNORECASE)
_BODY_CLOSE_RE = re.compile(r"</body\s*>", re.IGNORECASE)


def plain_to_html(text: str | None) -> str:
    """Escape plain-text signature/snippet and keep typed line breaks."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    return escape(cleaned).replace("\r\n", "\n").replace("\n", "<br>")


def _paragraphs(text: str) -> str:
    """Escaped body, blank-line separated, single newlines kept as breaks.

    Someone writing a reply presses Enter and expects a line break; HTML
    would otherwise collapse it into a space.
    """
    blocks = [b for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(
        f'<p style="margin:0 0 12px;">{escape(b).replace(chr(10), "<br>")}</p>' for b in blocks
    )


def render_plain(*, body: str, signature: str = "", agent_signature: str = "") -> str:
    """The text/plain part.

    Kept as the real alternative and not a stripped afterthought: a client
    that prefers text should get something a person can read, with the
    organisation/mailbox signature separated by the ``-- `` convention mail
    readers know.

    The agent's sign-off goes above that delimiter, with the message: it
    is who wrote the reply, and everything below ``-- `` is what a mail
    reader is entitled to collapse as boilerplate.
    """
    body = (body or "").strip()
    signature = (signature or "").strip()
    agent_signature = (agent_signature or "").strip()

    if agent_signature:
        body = f"{body}\n\n{agent_signature}" if body else agent_signature
    if not signature:
        return body
    return f"{body}\n\n-- \n{signature}"


def render_html(
    *,
    body: str,
    signature: str = "",
    logo_url: str = "",
    agent_signature: str = "",
    user_signature_html: str | None = None,
    org_signature_html: str | None = None,
) -> str:
    """The text/html part: the message, the writer, then the letterhead."""
    parts = [
        f'<body style="{_BODY}">',
        f'<div style="{_CARD}">',
        _paragraphs((body or "").strip()),
    ]

    agent_markup = (
        user_signature_html.strip()
        if user_signature_html is not None
        else plain_to_html(agent_signature)
    )
    if agent_markup:
        parts.append(f'<div style="{_AGENT}">{agent_markup}</div>')

    org_markup = (
        org_signature_html.strip() if org_signature_html is not None else plain_to_html(signature)
    )
    logo_url = (logo_url or "").strip()
    if org_markup or logo_url:
        parts.append(f'<hr style="{_RULE}">')
        if logo_url:
            # alt is empty on purpose: the signature below already names
            # the sender, and a blocked image should leave a gap, not the
            # word "logo".
            parts.append(f'<img src="{escape(logo_url, quote=True)}" alt="" style="{_LOGO}">')
        if org_markup:
            parts.append(f'<div style="{_SIGNATURE}">{org_markup}</div>')

    parts.append("</div></body>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Placeholders for templates and signatures
# ---------------------------------------------------------------------------
PLACEHOLDER_CONTENT = "{{contenido}}"
PLACEHOLDER_SIGNATURE = "{{firma}}"
PLACEHOLDER_ORG_SIGNATURE = "{{firma_organizacion}}"
PLACEHOLDER_LOGO = "{{logo}}"
# Legacy placeholder for the replying agent's signature; kept alongside
# ``{{firma}}`` (user signature, falling back to organisation signature) and
# ``{{firma_organizacion}}`` (organisation signature).
PLACEHOLDER_AGENT = "{{firma_agente}}"

PLACEHOLDERS = (
    PLACEHOLDER_CONTENT,
    PLACEHOLDER_SIGNATURE,
    PLACEHOLDER_ORG_SIGNATURE,
    PLACEHOLDER_AGENT,
    PLACEHOLDER_LOGO,
)

# User profile variables available inside rich signatures (and plain text ones).
SIG_VAR_NAME = "{{nombre}}"
SIG_VAR_JOB_TITLE = "{{cargo}}"
SIG_VAR_EMAIL = "{{correo}}"
SIG_VAR_PHONE = "{{telefono}}"
SIG_VAR_PHOTO = "{{foto}}"
SIG_VAR_PHOTO_URL = "{{foto_url}}"

SIGNATURE_VARIABLES = (
    SIG_VAR_NAME,
    SIG_VAR_JOB_TITLE,
    SIG_VAR_EMAIL,
    SIG_VAR_PHONE,
    SIG_VAR_PHOTO,
    SIG_VAR_PHOTO_URL,
)


def render_signature_variables(
    html: str,
    *,
    name: str = "",
    job_title: str = "",
    email: str = "",
    phone: str = "",
    avatar_url: str = "",
) -> str:
    """Substitute user profile variables into a sanitized signature HTML.

    Every value is escaped so a user's profile fields can never inject markup.
    """
    if not html:
        return ""
    clean_name = (name or "").strip()
    clean_url = (avatar_url or "").strip()
    safe_url = (
        escape(clean_url, quote=True) if clean_url and _SAFE_PHOTO_URL_RE.match(clean_url) else ""
    )
    photo_tag = (
        f'<img src="{safe_url}" alt="{escape(clean_name, quote=True)}" '
        f'width="48" height="48" style="{_AVATAR}" />'
        if safe_url
        else ""
    )
    return (
        html.replace(SIG_VAR_NAME, escape(clean_name))
        .replace(SIG_VAR_JOB_TITLE, escape((job_title or "").strip()))
        .replace(SIG_VAR_EMAIL, escape((email or "").strip()))
        .replace(SIG_VAR_PHONE, escape((phone or "").strip()))
        .replace(SIG_VAR_PHOTO, photo_tag)
        .replace(SIG_VAR_PHOTO_URL, safe_url)
    )


def render_signature_variables_plain(
    text: str,
    *,
    name: str = "",
    job_title: str = "",
    email: str = "",
    phone: str = "",
) -> str:
    """Substitute user profile variables into a plain-text signature."""
    if not text:
        return ""
    return (
        text.replace(SIG_VAR_NAME, (name or "").strip())
        .replace(SIG_VAR_JOB_TITLE, (job_title or "").strip())
        .replace(SIG_VAR_EMAIL, (email or "").strip())
        .replace(SIG_VAR_PHONE, (phone or "").strip())
        .replace(SIG_VAR_PHOTO, "")
        .replace(SIG_VAR_PHOTO_URL, "")
    )


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
            f"La plantilla tiene que incluir {PLACEHOLDER_CONTENT}, que es donde va el mensaje."
        )


def _append_signature(html: str, signature_markup: str) -> str:
    """Append the resolved signature at the bottom of a template without variables."""
    block = f'<div style="{_APPENDED_SIG}">{signature_markup}</div>'
    if _BODY_CLOSE_RE.search(html):
        return _BODY_CLOSE_RE.sub(lambda m: f"{block}{m.group(0)}", html, count=1)
    return f"{html}{block}"


def render_template(
    *,
    template: str,
    body: str,
    signature: str = "",
    logo_url: str = "",
    agent_signature: str = "",
    user_signature_html: str | None = None,
    org_signature_html: str | None = None,
    append_signature_if_missing: bool = False,
) -> str:
    """Fill an email template with the reply body, logo and resolved signatures.

    Falls back to :func:`render_html` when there is no template, so the
    built-in layout stays the default rather than something to opt into.

    Signature rules when rich signatures or ``append_signature_if_missing``
    are in play:
      * ``{{firma}}`` expands to the user's signature (designed HTML or
        escaped plain text) when present; otherwise the organisation's.
      * ``{{firma_organizacion}}`` always expands to the organisation's.
      * ``{{firma_agente}}`` expands to the user's signature.
      * If the template includes none of those variables and a signature
        exists, it is appended at the end so replies never silently lose it.
    """
    if not template.strip():
        return render_html(
            body=body,
            signature=signature,
            logo_url=logo_url,
            agent_signature=agent_signature,
            user_signature_html=user_signature_html,
            org_signature_html=org_signature_html,
        )

    logo_url = (logo_url or "").strip()
    logo_tag = (
        f'<img src="{escape(logo_url, quote=True)}" alt="" style="{_LOGO}">' if logo_url else ""
    )

    rich_mode = (
        user_signature_html is not None
        or org_signature_html is not None
        or append_signature_if_missing
    )

    if not rich_mode:
        sig_html = plain_to_html(signature)
        agent_html = plain_to_html(agent_signature)
        return (
            template.replace(PLACEHOLDER_CONTENT, _paragraphs((body or "").strip()))
            .replace(PLACEHOLDER_SIGNATURE, sig_html)
            .replace(PLACEHOLDER_ORG_SIGNATURE, sig_html)
            .replace(PLACEHOLDER_AGENT, agent_html)
            .replace(PLACEHOLDER_LOGO, logo_tag)
        )

    user_sig = (
        user_signature_html.strip()
        if user_signature_html is not None
        else plain_to_html(agent_signature)
    )
    org_sig = (
        org_signature_html.strip() if org_signature_html is not None else plain_to_html(signature)
    )
    effective_firma = user_sig or org_sig

    has_sig_placeholder = any(
        token in template
        for token in (
            PLACEHOLDER_SIGNATURE,
            PLACEHOLDER_ORG_SIGNATURE,
            PLACEHOLDER_AGENT,
        )
    )

    rendered = (
        template.replace(PLACEHOLDER_CONTENT, _paragraphs((body or "").strip()))
        .replace(PLACEHOLDER_SIGNATURE, effective_firma)
        .replace(PLACEHOLDER_ORG_SIGNATURE, org_sig)
        .replace(PLACEHOLDER_AGENT, user_sig)
        .replace(PLACEHOLDER_LOGO, logo_tag)
    )

    if append_signature_if_missing and not has_sig_placeholder and effective_firma:
        rendered = _append_signature(rendered, effective_firma)

    return rendered


__all__ = [
    "PLACEHOLDERS",
    "PLACEHOLDER_AGENT",
    "PLACEHOLDER_CONTENT",
    "PLACEHOLDER_LOGO",
    "PLACEHOLDER_ORG_SIGNATURE",
    "PLACEHOLDER_SIGNATURE",
    "SIGNATURE_VARIABLES",
    "SIG_VAR_EMAIL",
    "SIG_VAR_JOB_TITLE",
    "SIG_VAR_NAME",
    "SIG_VAR_PHONE",
    "SIG_VAR_PHOTO",
    "SIG_VAR_PHOTO_URL",
    "TemplateError",
    "plain_to_html",
    "render_html",
    "render_plain",
    "render_signature_variables",
    "render_signature_variables_plain",
    "render_template",
    "validate_template",
]
