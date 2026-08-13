"""Credential resolution for the meta_ads integration hook.

The ad account id and token are pasted in by an admin from the Integrations
tab, so the resolver has to cope with whichever field the form filled and
refuse to run on a half-configured hook.
"""

from __future__ import annotations

import pytest

from app.core.models_registry import import_all_models
from app.domains.ads.service import META_ADS_APP_ID, _credential_of
from app.domains.integrations.models import INTEGRATION_APPS, IntegrationsHook

import_all_models()

pytestmark = pytest.mark.unit


def _hook(**over) -> IntegrationsHook:
    base = {
        "account_id": 1,
        "app_id": META_ADS_APP_ID,
        "reference_id": None,
        "access_token": None,
        "settings": {},
    }
    base.update(over)
    return IntegrationsHook(**base)


def test_meta_ads_is_registered_as_an_integration_app():
    """Without the registry entry the Integrations tab has nothing to
    connect, and the hook the sync looks for could never be created."""
    app = next((a for a in INTEGRATION_APPS if a.id == META_ADS_APP_ID), None)
    assert app is not None
    assert app.hook_type == "account"
    # An inline settings form, not an OAuth redirect.
    assert app.action == "/meta_ads"


def test_reads_the_id_from_reference_id():
    got = _credential_of(_hook(reference_id="act_123", access_token="TK"))
    assert got == ("act_123", "TK")


def test_falls_back_to_settings_for_both_fields():
    """The generic hook form writes into ``settings``; accept that shape
    too rather than making the admin know which field the API used."""
    got = _credential_of(
        _hook(settings={"ad_account_id": "999", "access_token": "TK2"})
    )
    assert got == ("999", "TK2")


@pytest.mark.parametrize(
    "hook",
    [
        _hook(),  # nothing configured
        _hook(reference_id="act_123"),  # id but no token
        _hook(access_token="TK"),  # token but no id
    ],
)
def test_a_half_configured_hook_yields_nothing(hook):
    """Better to skip the account than to call Meta with a missing half and
    log an auth failure that looks like a revoked token."""
    assert _credential_of(hook) is None
