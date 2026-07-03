"""Unit tests for ``resolve_action`` — the Connect-URL resolver.

Mirrors ``Integrations::App#action``: inline apps return a relative path,
OAuth apps get their authorize URL augmented with the configured client
id + callback redirect (or ``None`` when unconfigured).
"""

from __future__ import annotations

import pytest

from app.domains.integrations.models import find_app, resolve_action

pytestmark = pytest.mark.unit


def _action(app_id, **client_ids):
    return resolve_action(
        find_app(app_id), client_ids=client_ids, app_base_url="http://app.test"
    )


def test_oauth_app_needs_a_client_id():
    assert _action("slack", slack=None) is None
    assert _action("slack") is None


def test_slack_action_is_augmented_when_configured():
    url = _action("slack", slack="CID123")
    assert url is not None
    # Base scope URL already has a query string → the params join with '&'.
    assert url.startswith("https://slack.com/oauth/v2/authorize?scope=")
    assert "&client_id=CID123" in url
    assert (
        "&redirect_uri=http://app.test/api/v1/integrations/slack/callback"
        in url
    )


def test_linear_uses_question_mark_separator():
    # The linear authorize URL has no query string, so params start with '?'.
    url = _action("linear", linear="L1")
    assert url == (
        "https://linear.app/oauth/authorize?client_id=L1"
        "&redirect_uri=http://app.test/api/v1/integrations/linear/callback"
    )


def test_inline_apps_return_relative_action_verbatim():
    assert _action("dialogflow") == "/dialogflow"
    assert _action("openai") == "/openai"
    assert _action("webhook") == "/webhook"


def test_apps_without_action_stay_none():
    assert _action("shopify") is None
    assert _action("notion") is None


def test_hook_type_metadata():
    assert find_app("dialogflow").hook_type == "inbox"
    assert find_app("slack").hook_type == "account"
