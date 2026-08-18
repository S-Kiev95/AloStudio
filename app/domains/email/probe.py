"""Try a mailbox's credentials and say what happened.

Configuring IMAP and SMTP is a form with eight fields, half of them
hostnames that differ by three characters. Nothing in the product tried
them, so a mailbox with a typo looked configured and simply never
delivered — the first sign was mail not arriving, days later, with no
error anywhere to explain it.

Each side is probed independently and neither raises: a report saying
which one failed and why is the whole point, so an exception here would
defeat it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.domains.inboxes.models import EmailChannel

log = logging.getLogger(__name__)

_TIMEOUT = 20.0


@dataclass
class SideResult:
    """One side's outcome. ``ok`` False always carries a reason."""

    configured: bool
    ok: bool = False
    error: str | None = None


@dataclass
class ProbeResult:
    imap: SideResult
    smtp: SideResult


def _hint(raw: str, *, host: str, expected_prefix: str) -> str:
    """Turn a protocol error into something actionable.

    A certificate mismatch is the signature of the two hostnames being
    swapped — the commonest way this gets filled in wrong — and saying so
    beats echoing an OpenSSL string nobody can act on.
    """
    lowered = raw.lower()
    if "certificate" in lowered and "hostname mismatch" in lowered:
        return (
            f"El servidor {host} no es el correcto para esta parte: "
            f"suele empezar con {expected_prefix}"
        )
    if "authenticationfailed" in lowered or "invalid credentials" in lowered:
        return (
            "Usuario o contraseña incorrectos. En Gmail y Outlook con "
            "verificación en dos pasos hay que usar una contraseña de "
            "aplicación, no la de la cuenta."
        )
    if "auth extension is not supported" in lowered:
        # A host that answers but has no AUTH is almost never an SMTP
        # server — the usual cause is the IMAP hostname in the SMTP box.
        return (
            f"{host} respondió, pero no acepta autenticación SMTP. "
            f"Probablemente no sea un servidor de envío: suele empezar "
            f"con {expected_prefix}"
        )
    if "timed out" in lowered or "timeout" in lowered:
        return (
            f"No respondió {host}. Revisá el servidor y el puerto — y que "
            "la conexión segura esté activada, porque un puerto cifrado no "
            "contesta en claro."
        )
    return raw[:200]


async def _probe_imap(channel: EmailChannel) -> SideResult:
    if not channel.imap_enabled:
        return SideResult(configured=False)
    try:
        import aioimaplib

        # The same class the poller picks. Hardcoding IMAP4_SSL made this
        # report a connection the product never makes: a channel with
        # ``imap_enable_ssl`` off passed here and then timed out on every
        # real fetch, which is worse than having no test at all.
        cls = (
            aioimaplib.IMAP4_SSL
            if channel.imap_enable_ssl
            else aioimaplib.IMAP4
        )
        client = cls(
            host=channel.imap_address,
            port=channel.imap_port or 993,
            timeout=_TIMEOUT,
        )
        await client.wait_hello_from_server()
        res = await client.login(channel.imap_login, channel.imap_password)
        if res.result != "OK":
            detail = b" ".join(res.lines).decode("utf-8", "replace")
            return SideResult(
                configured=True,
                error=_hint(
                    detail, host=channel.imap_address, expected_prefix="imap."
                ),
            )
        # Logging in is not enough: a mailbox we cannot open delivers
        # nothing, and that failure would otherwise surface as silence.
        selected = await client.select("INBOX")
        await client.logout()
        if selected.result != "OK":
            return SideResult(
                configured=True, error="Entró, pero no pudo abrir INBOX."
            )
        return SideResult(configured=True, ok=True)
    except Exception as exc:  # noqa: BLE001 - reporting is the point
        return SideResult(
            configured=True,
            error=_hint(
                f"{type(exc).__name__}: {exc}",
                host=channel.imap_address,
                expected_prefix="imap.",
            ),
        )


async def _probe_smtp(channel: EmailChannel) -> SideResult:
    if not channel.smtp_enabled:
        return SideResult(configured=False)
    try:
        import aiosmtplib

        smtp = aiosmtplib.SMTP(
            hostname=channel.smtp_address,
            port=channel.smtp_port or 587,
            use_tls=channel.smtp_enable_ssl_tls,
            start_tls=channel.smtp_enable_starttls_auto
            and not channel.smtp_enable_ssl_tls,
            timeout=_TIMEOUT,
        )
        await smtp.connect()
        if channel.smtp_login:
            await smtp.login(channel.smtp_login, channel.smtp_password)
        await smtp.quit()
        return SideResult(configured=True, ok=True)
    except Exception as exc:  # noqa: BLE001 - reporting is the point
        return SideResult(
            configured=True,
            error=_hint(
                f"{type(exc).__name__}: {exc}",
                host=channel.smtp_address,
                expected_prefix="smtp.",
            ),
        )


async def probe_email_channel(channel: EmailChannel) -> ProbeResult:
    """Try both sides. Never raises."""
    return ProbeResult(
        imap=await _probe_imap(channel), smtp=await _probe_smtp(channel)
    )


__all__ = ["ProbeResult", "SideResult", "probe_email_channel"]
