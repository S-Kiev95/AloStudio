"""Credentials must not reach a log file.

Graph API calls carry the page token in the query string and httpx logs the
whole request line at INFO, so an ordinary request log used to write a live,
long-lived token to disk on the server.

The token strings here are fabricated — shaped like Meta's so the patterns
are exercised, but not credentials.
"""

from __future__ import annotations

import logging

import pytest

from app.core.logging import (
    REDACTED,
    SecretRedactingFilter,
    install_secret_redaction,
    redact_processor,
    scrub_secrets,
)

pytestmark = pytest.mark.unit

FAKE_TOKEN = "EAARvf4mPcjUBRZC9ZCn05KsoOjZBVOBaYTNRSWZCudANbSRhK5Hnw"


def _record(msg: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args or None,
        exc_info=None,
    )


def _filtered(msg: str, *args: object) -> str:
    record = _record(msg, *args)
    assert SecretRedactingFilter().filter(record) is True
    return record.getMessage()


class TestScrubbing:
    def test_removes_a_token_from_a_query_string(self):
        line = f"GET https://graph.facebook.com/v23.0/me?fields=id&access_token={FAKE_TOKEN}"
        out = scrub_secrets(line)
        assert FAKE_TOKEN not in out
        assert f"access_token={REDACTED}" in out
        # The rest of the URL is what makes the log useful — keep it.
        assert "graph.facebook.com/v23.0/me" in out
        assert "fields=id" in out

    def test_keeps_a_following_parameter(self):
        """A greedy match would swallow everything after the token."""
        out = scrub_secrets(
            f"https://graph.facebook.com/me?access_token={FAKE_TOKEN}&limit=25"
        )
        assert FAKE_TOKEN not in out
        assert "limit=25" in out

    @pytest.mark.parametrize(
        "param",
        [
            "access_token",
            "client_secret",
            "refresh_token",
            "app_secret",
            "appsecret_proof",
        ],
    )
    def test_covers_every_credential_parameter(self, param: str):
        assert "s3cret" not in scrub_secrets(f"https://x/y?{param}=s3cret")

    def test_removes_a_bearer_header(self):
        out = scrub_secrets("Authorization: Bearer abc.def-123")
        assert "abc.def-123" not in out
        assert f"Bearer {REDACTED}" in out

    def test_removes_a_bare_meta_token(self):
        """A token reaching a log by some route the URL pattern misses."""
        out = scrub_secrets(f"token refresh failed for {FAKE_TOKEN}")
        assert FAKE_TOKEN not in out

    def test_leaves_ordinary_text_alone(self):
        line = "instagram.autoreply.queued comment=18466 reason=keyword"
        assert scrub_secrets(line) == line

    def test_does_not_mangle_a_word_containing_token(self):
        line = "tokenizer produced 12 tokens"
        assert scrub_secrets(line) == line


class TestFilter:
    def test_scrubs_a_url_passed_as_an_argument(self):
        """httpx logs the URL as a ``%s`` arg, not inside the message."""
        out = _filtered(
            'HTTP Request: %s %s "%s %d %s"',
            "GET",
            f"https://graph.facebook.com/v23.0/me?access_token={FAKE_TOKEN}",
            "HTTP/1.1",
            200,
            "OK",
        )
        assert FAKE_TOKEN not in out
        assert "HTTP Request: GET" in out
        assert "200 OK" in out

    def test_scrubs_a_non_string_argument(self):
        """httpx passes an ``httpx.URL`` object, not a str."""

        class Url:
            def __str__(self) -> str:
                return f"https://graph.facebook.com/me?access_token={FAKE_TOKEN}"

        out = _filtered("HTTP Request: %s %s", "GET", Url())
        assert FAKE_TOKEN not in out
        assert REDACTED in out

    def test_keeps_numeric_arguments_numeric(self):
        """Stringifying an int would raise inside a ``%d`` format."""
        record = _record("status %d after %s", 200, "retry")
        SecretRedactingFilter().filter(record)
        assert record.args == (200, "retry")
        assert record.getMessage() == "status 200 after retry"

    def test_scrubs_dict_style_arguments(self):
        record = _record(
            "calling %(url)s", {"url": f"https://x/y?access_token={FAKE_TOKEN}"}
        )
        SecretRedactingFilter().filter(record)
        assert FAKE_TOKEN not in record.getMessage()

    def test_survives_an_argument_whose_str_raises(self):
        class Broken:
            def __str__(self) -> str:
                raise RuntimeError("boom")

        record = _record("value %r", Broken())
        assert SecretRedactingFilter().filter(record) is True

    def test_the_record_is_rewritten_not_just_the_formatted_line(self):
        """Handlers added after the filter ran must see the clean record."""
        record = _record("access_token=%s", FAKE_TOKEN)
        SecretRedactingFilter().filter(record)
        assert FAKE_TOKEN not in str(record.args)


class TestInstall:
    def test_attaches_to_the_http_loggers(self):
        install_secret_redaction()
        assert any(
            isinstance(f, SecretRedactingFilter)
            for f in logging.getLogger("httpx").filters
        )

    def test_is_idempotent(self):
        """Called by both the app and the worker entry point."""
        logger = logging.getLogger("httpx")
        install_secret_redaction()
        install_secret_redaction()
        installed = [
            f for f in logger.filters if isinstance(f, SecretRedactingFilter)
        ]
        assert len(installed) == 1

    def test_structlog_is_covered_too(self):
        """structlog writes through its own logger, bypassing the filter."""
        event = redact_processor(
            None,
            "info",
            {
                "event": "graph_call_failed",
                "url": f"https://graph.facebook.com/me?access_token={FAKE_TOKEN}",
                "status": 400,
            },
        )
        assert FAKE_TOKEN not in event["url"]
        assert event["status"] == 400  # non-strings pass through untouched

    def test_structlog_scrubs_an_exception_value(self):
        event = redact_processor(
            None, "warning", {"err": RuntimeError(f"denied for {FAKE_TOKEN}")}
        )
        assert FAKE_TOKEN not in str(event["err"])

    def test_an_httpx_log_comes_out_clean_end_to_end(self, caplog):
        install_secret_redaction()
        with caplog.at_level(logging.INFO, logger="httpx"):
            logging.getLogger("httpx").info(
                'HTTP Request: %s %s "%s %d %s"',
                "GET",
                f"https://graph.facebook.com/v23.0/me?access_token={FAKE_TOKEN}",
                "HTTP/1.1",
                200,
                "OK",
            )
        assert FAKE_TOKEN not in caplog.text
        assert REDACTED in caplog.text
