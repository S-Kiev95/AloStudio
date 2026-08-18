"""Trying a mailbox's credentials and saying something useful about it.

Configuring IMAP and SMTP is eight fields, half of them hostnames that
differ by three characters. Nothing tried them before, so a typo left the
mailbox looking configured and silently delivering nothing — the first
sign was mail not arriving days later. What matters here is that a failure
produces a sentence someone can act on, not an OpenSSL string.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domains.email import probe as probe_mod
from app.domains.email.probe import probe_email_channel

pytestmark = pytest.mark.unit


def _channel(**over):
    base = {
        "imap_enabled": True,
        "imap_address": "imap.gmail.com",
        "imap_port": 993,
        "imap_login": "yo@gmail.com",
        "imap_password": "x",
        "smtp_enabled": True,
        "smtp_address": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_login": "yo@gmail.com",
        "smtp_password": "x",
        "smtp_enable_ssl_tls": False,
        "smtp_enable_starttls_auto": True,
    }
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def sides(monkeypatch):
    """Drive both probes without touching a mail server."""

    def _set(*, imap=None, smtp=None):
        async def _imap(channel):
            if imap is None:
                return probe_mod.SideResult(configured=True, ok=True)
            raise imap

        async def _smtp(channel):
            if smtp is None:
                return probe_mod.SideResult(configured=True, ok=True)
            raise smtp

        monkeypatch.setattr(probe_mod, "_probe_imap", _imap)
        monkeypatch.setattr(probe_mod, "_probe_smtp", _smtp)

    return _set


class TestReporting:
    async def test_a_side_that_is_off_is_not_an_error(self):
        """Send-only and receive-only are real configurations."""
        result = await probe_email_channel(
            _channel(imap_enabled=False, smtp_enabled=False)
        )
        assert result.imap.configured is False
        assert result.imap.error is None
        assert result.smtp.configured is False


class TestHints:
    """The sentence a failure produces is the whole feature."""

    def test_a_certificate_mismatch_names_the_swapped_hostname(self):
        out = probe_mod._hint(
            "SSLCertVerificationError: certificate verify failed: "
            "Hostname mismatch, certificate is not valid for 'imap.gmail.com'.",
            host="imap.gmail.com",
            expected_prefix="smtp.",
        )
        assert "imap.gmail.com" in out
        assert "smtp." in out
        # Not the OpenSSL string, which nobody can act on.
        assert "_ssl.c" not in out

    def test_a_host_without_auth_is_probably_the_wrong_one(self):
        out = probe_mod._hint(
            "SMTPException: The SMTP AUTH extension is not supported by "
            "this server.",
            host="imap.gmail.com",
            expected_prefix="smtp.",
        )
        assert "no acepta autenticación SMTP" in out
        assert "smtp." in out

    def test_the_same_error_on_a_correct_host_blames_the_encryption(self):
        """One error, two causes, and the advice differs.

        On a host that is already an SMTP one the cause is the connection
        not being encrypted — providers refuse AUTH in the clear. Blaming
        the hostname there sends someone to change a correct field, which
        is what the first version of this message did.
        """
        out = probe_mod._hint(
            "SMTPException: The SMTP AUTH extension is not supported by "
            "this server.",
            host="smtp.gmail.com",
            expected_prefix="smtp.",
        )
        assert "STARTTLS" in out
        assert "no sea un servidor de envío" not in out

    def test_bad_credentials_mention_the_app_password(self):
        # The commonest real cause, and the one nobody guesses.
        out = probe_mod._hint(
            "[AUTHENTICATIONFAILED] Invalid credentials (Failure)",
            host="imap.gmail.com",
            expected_prefix="imap.",
        )
        assert "contraseña de aplicación" in out

    def test_a_timeout_points_at_the_host_and_port(self):
        out = probe_mod._hint(
            "TimeoutError: timed out", host="imap.raro.com", expected_prefix="imap."
        )
        assert "imap.raro.com" in out
        assert "puerto" in out

    def test_an_unrecognised_error_is_passed_through_trimmed(self):
        out = probe_mod._hint(
            "Algo muy raro " + "x" * 500, host="h", expected_prefix="imap."
        )
        assert out.startswith("Algo muy raro")
        assert len(out) <= 200

    def test_the_hint_does_not_read_with_a_double_stop(self):
        out = probe_mod._hint(
            "The SMTP AUTH extension is not supported by this server.",
            host="h",
            expected_prefix="smtp.",
        )
        assert ".." not in out


class TestItTestsWhatTheProductDoes:
    """The probe has to make the connection the poller makes.

    Hardcoding IMAP4_SSL reported success for a channel with SSL off — and
    that channel then timed out on every real fetch. A test that certifies
    a broken configuration is worse than no test.
    """

    async def test_it_connects_the_way_the_poller_will(self, monkeypatch):
        used: list[str] = []

        class _Client:
            def __init__(self, **kwargs):
                pass

            async def wait_hello_from_server(self):
                return None

            async def login(self, *_a):
                return SimpleNamespace(result="OK", lines=[b""])

            async def select(self, *_a):
                return SimpleNamespace(result="OK")

            async def logout(self):
                return None

        class _Fake:
            @staticmethod
            def IMAP4_SSL(**kwargs):  # noqa: N802 - mirrors aioimaplib
                used.append("ssl")
                return _Client()

            @staticmethod
            def IMAP4(**kwargs):  # noqa: N802 - mirrors aioimaplib
                used.append("plain")
                return _Client()

        monkeypatch.setitem(__import__("sys").modules, "aioimaplib", _Fake)

        await probe_mod._probe_imap(_channel(imap_enable_ssl=True))
        await probe_mod._probe_imap(_channel(imap_enable_ssl=False))
        assert used == ["ssl", "plain"]

    def test_a_timeout_mentions_the_security_switch(self):
        # A cipher-only port simply does not answer in the clear, and that
        # is exactly how the flag being off presents.
        out = probe_mod._hint(
            "TimeoutError: ", host="imap.gmail.com", expected_prefix="imap."
        )
        assert "conexión segura" in out
