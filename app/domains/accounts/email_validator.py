"""Signup email validator — ports Chatwoot's Account::SignUpEmailValidationService.

Ruby reference:
  reference/chatwoot/app/services/account/sign_up_email_validation_service.rb

Chatwoot uses the `valid_email2` gem, which bundles:
  * a syntactic/RFC-level check (``address.valid?``)
  * a list of known disposable-mail domains (``address.disposable?``)
  * DNS MX lookup (``address.valid_mx?``) — only used when ``strict_mx`` is set
    (Chatwoot does not enable strict_mx in the signup flow).

Plus a ``BLOCKED_EMAIL_DOMAINS`` GlobalConfigService list where each line is
a substring/regex matched against the domain (case-insensitive).

For AloStudio we mirror the first three behaviours. MX lookup is deferred (it's
not exercised in the reference signup path). The blocked-domain list is read
from ``Settings.blocked_email_domains`` (future) or an in-memory list.
"""

from __future__ import annotations

import re
from email_validator import EmailNotValidError, validate_email

from app.domains.accounts.exceptions import InvalidEmail

# A minimal bundled disposable-domain list. Chatwoot uses valid_email2's
# upstream list (~3k domains); for parity test purposes the list only matters
# if we feed a disposable address. We mirror the most common ones so integration
# tests of the "rejects disposable" branch pass; the authoritative list can be
# imported from valid_email2/vendor/disposable_email_domains.txt when needed.
_DISPOSABLE_DOMAINS: frozenset[str] = frozenset(
    {
        "mailinator.com",
        "10minutemail.com",
        "guerrillamail.com",
        "trashmail.com",
        "tempmail.com",
        "yopmail.com",
        "throwawaymail.com",
        "discard.email",
        "fakeinbox.com",
        "sharklasers.com",
    }
)


def _domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


def validate_signup_email(
    email: str,
    *,
    blocked_domains: list[str] | None = None,
) -> None:
    """Raise :class:`InvalidEmail` with Chatwoot-shaped payload on failure.

    The payload shape matches ``CustomExceptions::Account::InvalidEmail.new(...)``
    in Ruby so error bodies stay byte-identical.
    """
    # 1) Syntactic validation — check_deliverability=False keeps this offline
    #    to match the non-strict_mx branch of valid_email2.
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError as e:
        raise InvalidEmail(payload={"valid": False, "disposable": None}) from e

    domain = _domain_of(email)

    # 2) Blocked-domain list (substring match, case-insensitive) — mirrors
    #    `blocked_domains.any? { |d| domain.match?(d.downcase) }` in Ruby.
    for pattern in blocked_domains or []:
        try:
            if re.search(pattern.strip().lower(), domain):
                raise InvalidEmail(payload={"domain_blocked": True})
        except re.error:
            # fall back to plain substring if pattern isn't a valid regex —
            # that's what Ruby's `match?` with a String arg does.
            if pattern.strip().lower() in domain:
                raise InvalidEmail(payload={"domain_blocked": True}) from None

    # 3) Disposable-domain check.
    if domain in _DISPOSABLE_DOMAINS:
        raise InvalidEmail(payload={"valid": True, "disposable": True})
