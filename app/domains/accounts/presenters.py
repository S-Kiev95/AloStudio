"""Account response shaping.

Ports ``reference/chatwoot/app/views/api/v1/models/_account.json.jbuilder``
+ ``accounts/show.json.jbuilder`` + ``accounts/update.json.jbuilder``.

The jbuilder partial only emits the subset of ``custom_attributes`` keys
Chatwoot considers "known" — arbitrary keys in the JSONB column are not
echoed back. We keep that behaviour for parity (otherwise frontend code
branching on unknown keys changes).
"""

from __future__ import annotations

from typing import Any

from app.domains.accounts.models import Account

# The exact key whitelist from _account.json.jbuilder (lines 5-17).
_CUSTOM_ATTRIBUTE_KEYS_ALWAYS = (
    "plan_name",
    "subscribed_quantity",
    "subscription_status",
    "subscription_ends_on",
)
_CUSTOM_ATTRIBUTE_KEYS_IF_PRESENT = (
    "industry",
    "company_size",
    "timezone",
    "logo",
    "onboarding_step",
    "marked_for_deletion_at",
    "marked_for_deletion_reason",
)


def _custom_attrs_view(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the whitelisted custom_attributes or ``None`` if raw is empty.

    The Rails template wraps the whole ``custom_attributes`` block in
    ``if resource.custom_attributes.present?`` — omit the key entirely
    when the column is empty so JSON parity holds.
    """
    if not raw:
        return None
    out: dict[str, Any] = {}
    for k in _CUSTOM_ATTRIBUTE_KEYS_ALWAYS:
        # Rails emits these unconditionally (nil becomes json null).
        out[k] = raw.get(k)
    for k in _CUSTOM_ATTRIBUTE_KEYS_IF_PRESENT:
        if raw.get(k):
            out[k] = raw[k]
    return out


def present_account_show(account: Account, *, latest_chatwoot_version: str | None = None) -> dict:
    """Shape of ``GET /api/v1/accounts/:id`` + ``PATCH /api/v1/accounts/:id``.

    ``features`` and ``cache_keys`` are stubbed for Phase 1:

      * ``features`` = ``{}`` until the feature-flag subsystem lands
        (Chatwoot reads from Flipper-style bitmap on ``feature_flags`` col).
      * ``cache_keys`` = ``{}`` until the Redis cache-key subsystem lands.

    Neither field is consumed by auth/profile/signup flows, so the empty
    values don't perturb the parity suite for Phase 1 scope.
    """
    body: dict[str, Any] = {
        "settings": account.settings or {},
        "created_at": account.created_at,
        "domain": account.domain,
        "features": {},  # Phase 1 stub — see note above.
        "id": account.id,
        "locale": account.locale,
        "name": account.name,
        "support_email": account.support_email,
        "status": account.status,
        "cache_keys": {},  # Phase 1 stub.
    }

    ca = _custom_attrs_view(account.custom_attributes)
    if ca is not None:
        body["custom_attributes"] = ca

    if latest_chatwoot_version is not None:
        body["latest_chatwoot_version"] = latest_chatwoot_version

    return body
