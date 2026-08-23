"""Send a template to a real inbox so it can be judged where it lands.

The dashboard preview is a browser rendering, and a browser is the one
place this message will never be read. Outlook renders with Word's
engine, Gmail clips past ~102 KB, and most clients hide images until the
reader allows them — none of which a preview can show.

Sends through a mailbox's own SMTP settings, so it also proves the
transport that will carry the real replies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid

import aiosmtplib

from app.domains.email.template import render_plain
from app.domains.email.templates_service import (
    SAMPLE_AGENT_SIGNATURE,
    SAMPLE_BODY,
    render_sample,
)

log = logging.getLogger(__name__)


@dataclass(slots=True)
class TestSendResult:
    ok: bool
    error: str | None = None


def _hint(exc: Exception) -> str:
    """Turn a transport failure into something actionable.

    The same advice the connection probe gives, because the operator
    hitting this button is asking the same question.
    """
    text = str(exc)
    if isinstance(exc, aiosmtplib.SMTPAuthenticationError):
        return (
            "El servidor rechazó el usuario o la contraseña. Si es Gmail "
            "con verificación en dos pasos, hace falta una contraseña de "
            "aplicación, no la de la cuenta."
        )
    if isinstance(exc, TimeoutError):
        return (
            "El servidor no respondió a tiempo. Revisá el host y el puerto."
        )
    if "STARTTLS" in text or "SSL" in text or "TLS" in text:
        return (
            "Falló la negociación TLS. Suele ser el puerto: 465 va con SSL "
            "directo y 587 con STARTTLS."
        )
    return f"No se pudo enviar: {text[:200]}"


async def send_template_test(
    *, channel, to_address: str, template_html: str
) -> TestSendResult:
    """Mail the rendered template to ``to_address`` via ``channel``'s SMTP."""
    if not channel.smtp_enabled:
        return TestSendResult(
            ok=False,
            error=(
                "La casilla tiene el envío (SMTP) desactivado, así que no "
                "hay por dónde mandar la prueba."
            ),
        )
    if not channel.smtp_address:
        return TestSendResult(
            ok=False, error="La casilla no tiene servidor SMTP configurado."
        )

    mail = EmailMessage()
    mail["From"] = formataddr(("", channel.email or channel.smtp_login or ""))
    mail["To"] = to_address
    mail["Subject"] = "Prueba de plantilla — AloStudio"
    mail["Date"] = format_datetime(datetime.now(UTC))
    mail["Message-ID"] = make_msgid()
    # Marks it as automated so it never trips an out-of-office reply.
    mail["Auto-Submitted"] = "auto-generated"

    mail.set_content(
        render_plain(
            body=SAMPLE_BODY,
            signature=channel.signature or "",
            agent_signature=SAMPLE_AGENT_SIGNATURE,
        )
    )
    mail.add_alternative(
        render_sample(
            template_html=template_html,
            signature=channel.signature or "",
            logo_url=channel.logo_url or "",
        ),
        subtype="html",
    )

    try:
        await aiosmtplib.send(
            mail,
            hostname=channel.smtp_address,
            port=channel.smtp_port,
            username=channel.smtp_login or None,
            password=channel.smtp_password or None,
            use_tls=channel.smtp_enable_ssl_tls,
            start_tls=channel.smtp_enable_starttls_auto
            and not channel.smtp_enable_ssl_tls,
            timeout=20.0,
        )
    except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
        log.warning(
            "email.template_test.failed channel_id=%s error=%s",
            channel.id,
            type(exc).__name__,
        )
        return TestSendResult(ok=False, error=_hint(exc))

    return TestSendResult(ok=True)


__all__ = ["TestSendResult", "send_template_test"]
