"""Contact service layer — normalization + builder + identify + merge.

Ports three Chatwoot actors:
  * ``Contact#prepare_contact_attributes`` (``before_validation`` hook) —
    email downcasing + JSONB coercion (kept in :func:`normalize_contact_write`).
  * ``ContactInboxBuilder`` → :class:`ContactInboxBuilder`.
  * ``ContactIdentifyAction`` → :class:`ContactIdentifyAction`.
  * ``ContactMergeAction``   → :class:`ContactMergeAction`.

Phase 3 scope for merge:
  * Moves ``contact_inboxes`` and ``notes`` rows over to the base contact.
  * Deep-merges ``additional_attributes`` / ``custom_attributes`` with
    base-wins precedence.
  * **Skips** the Conversation + Message reassignment that Chatwoot does
    — those tables land in Phase 4. The skipped steps are no-ops with a
    log line so they're trivially wired in once Phase 4 arrives.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.contacts.models import Contact, ContactInbox, Note
from app.domains.inboxes.models import (
    CHANNEL_TYPE_API,
    CHANNEL_TYPE_EMAIL,
    CHANNEL_TYPE_FACEBOOK,
    CHANNEL_TYPE_INSTAGRAM,
    CHANNEL_TYPE_SMS,
    CHANNEL_TYPE_TELEGRAM,
    CHANNEL_TYPE_TWILIO_SMS,
    CHANNEL_TYPE_WEB_WIDGET,
    Inbox,
)

# E.164 international phone number — mirrors Chatwoot's regex exactly
# (``/\+[1-9]\d{1,14}\z/``). The Python port uses \Z to anchor at end-of-string
# so multi-line input doesn't slip through.
_PHONE_RE = re.compile(r"^\+[1-9]\d{1,14}\Z")

# Close-enough approximation of ``Devise.email_regexp`` for format validation.
# We don't need byte-for-byte regex parity because the wire-level behaviour
# only surfaces pass/fail; we just need the same set of values to pass.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+\Z")


# =========================================================================
# Write-side normalization (before_validation)
# =========================================================================
def normalize_contact_write(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply the same transforms Chatwoot's ``before_validation`` hook does.

    * Lowercase + null-coalesce ``email`` (blank → ``None`` so the unique
      index doesn't fire on ``''``).
    * Default ``additional_attributes`` and ``custom_attributes`` to
      ``{}`` when missing.
    * Leave ``phone_number`` / ``identifier`` alone here — format/uniqueness
      is enforced at save time by the DB index, and the E.164 check is
      applied in :func:`assert_valid_contact_identity` so failures surface
      as 422 not 500.
    """
    out = dict(payload)
    if "email" in out:
        email = out["email"]
        if email is None or (isinstance(email, str) and not email.strip()):
            out["email"] = None
        else:
            out["email"] = email.strip().lower()
    if "phone_number" in out and out["phone_number"] is not None:
        pn = out["phone_number"].strip()
        out["phone_number"] = pn or None
    if "identifier" in out and out["identifier"] is not None:
        ident = out["identifier"].strip()
        out["identifier"] = ident or None
    if out.get("additional_attributes") is None:
        out["additional_attributes"] = {}
    if out.get("custom_attributes") is None:
        out["custom_attributes"] = {}
    return out


def assert_valid_contact_identity(payload: dict[str, Any]) -> None:
    """Raise 422 if email/phone_number formats don't pass Chatwoot's validators.

    Unknown keys are ignored — the caller has already whitelisted what's
    allowed via the request schema.
    """
    email = payload.get("email")
    if email and not _EMAIL_RE.match(email):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Email is invalid"},
        )
    phone = payload.get("phone_number")
    if phone and not _PHONE_RE.match(phone):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Phone number should be in e164 format"},
        )


# =========================================================================
# ContactInboxBuilder
# =========================================================================
@dataclass
class ContactInboxBuilder:
    """Create-or-find a ContactInbox for (contact, inbox[, source_id]).

    Ported from ``reference/chatwoot/app/builders/contact_inbox_builder.rb``.

    For ``Channel::Api`` / ``Channel::WebWidget`` the ``source_id`` is a
    random UUID when the caller doesn't supply one. Other channel types
    will be wired in Phase 5 alongside their channel models (SMS, Email,
    WhatsApp, Twilio) — until then they raise ``NotImplementedError`` so
    a misrouted call surfaces as a 500 rather than a silently-wrong
    ContactInbox row.
    """

    session: AsyncSession
    contact: Contact
    inbox: Inbox
    source_id: str | None = None
    hmac_verified: bool = False

    async def perform(self) -> ContactInbox:
        source_id = self.source_id or self._generate_source_id()
        return await self._create_or_find(source_id)

    def _generate_source_id(self) -> str:
        if self.inbox.channel_type in (
            CHANNEL_TYPE_API,
            CHANNEL_TYPE_WEB_WIDGET,
        ):
            return str(uuid.uuid4())
        if self.inbox.channel_type == CHANNEL_TYPE_EMAIL:
            # Rails uses the contact's email as source_id for Email
            # channels — that's how the IMAP ingest finds the existing
            # ContactInbox when a familiar address sends another mail.
            # We mirror that exactly. Falls back to UUID when the
            # contact has no email yet (rare; mostly seeded fixtures).
            return self.contact.email or str(uuid.uuid4())
        if self.inbox.channel_type == CHANNEL_TYPE_FACEBOOK:
            # Facebook always passes the PSID explicitly via
            # ``source_id``; this fallback only fires if the caller
            # forgot to. UUID is the safest punt.
            return str(uuid.uuid4())
        if self.inbox.channel_type == CHANNEL_TYPE_INSTAGRAM:
            # Instagram, like Facebook, always passes the IGSID
            # explicitly via ``source_id``. UUID fallback for safety.
            return str(uuid.uuid4())
        if self.inbox.channel_type in (
            CHANNEL_TYPE_TWILIO_SMS,
            CHANNEL_TYPE_SMS,
        ):
            # Twilio + Bandwidth ingest both pass the contact's phone
            # number as source_id explicitly. UUID fallback for the
            # rare path where the caller forgot.
            return str(uuid.uuid4())
        if self.inbox.channel_type == CHANNEL_TYPE_TELEGRAM:
            # Telegram passes the user's ``from.id`` (a numeric IDs)
            # as source_id explicitly. UUID fallback only matters if
            # the caller forgot.
            return str(uuid.uuid4())
        raise NotImplementedError(
            f"ContactInboxBuilder doesn't support channel_type={self.inbox.channel_type!r} yet"
        )

    async def _create_or_find(self, source_id: str) -> ContactInbox:
        stmt = select(ContactInbox).where(
            ContactInbox.inbox_id == self.inbox.id,
            ContactInbox.source_id == source_id,
        )
        existing = (await self.session.exec(stmt)).first()
        if existing is not None:
            return existing

        row = ContactInbox(
            contact_id=self.contact.id,
            inbox_id=self.inbox.id,
            source_id=source_id,
            hmac_verified=self.hmac_verified,
        )
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            # The race-condition retry logic for non-live-chat channels
            # (``update_old_contact_inbox``) is deferred until Phase 5
            # when SMS/WA/Email channels exist. For API we just surface
            # the uniqueness error.
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "contact inbox already exists"},
            ) from e
        return row


# =========================================================================
# ContactMergeAction
# =========================================================================
@dataclass
class ContactMergeAction:
    """Fold ``mergee`` into ``base`` and delete ``mergee``.

    Ported from ``reference/chatwoot/app/actions/contact_merge_action.rb``.

    Phase-4 bits that are currently no-ops:
      * ``Conversation.where(contact_id: mergee).update(contact_id: base)``
      * ``Message.where(sender: mergee).update(sender: base)``
    Wired in as soon as those tables exist — this class is the single
    injection point (two TODO comments below mark the spots).
    """

    session: AsyncSession
    account_id: int
    base: Contact
    mergee: Contact

    async def perform(self) -> Contact:
        if self.base.id == self.mergee.id:
            return self.base

        self._validate_same_account()

        # Conversation + Message reassignment (Phase 3 deferred → Phase 4a).
        # Lives in the conversations service to keep the cross-domain
        # import one-way (contacts depends on conversations, not the
        # other direction).
        from app.domains.conversations.service import (
            reassign_mergee_conversations,
        )

        await reassign_mergee_conversations(
            self.session,
            mergee_contact_id=self.mergee.id,
            base_contact_id=self.base.id,
        )

        await self._merge_contact_inboxes()
        await self._merge_contact_notes()
        await self._merge_and_remove_mergee()
        return self.base

    def _validate_same_account(self) -> None:
        if (
            self.base.account_id != self.account_id
            or self.mergee.account_id != self.account_id
        ):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "contact does not belong to the account"},
            )

    async def _merge_contact_inboxes(self) -> None:
        await self.session.exec(
            update(ContactInbox)
            .where(ContactInbox.contact_id == self.mergee.id)
            .values(contact_id=self.base.id)
        )

    async def _merge_contact_notes(self) -> None:
        await self.session.exec(
            update(Note)
            .where(
                Note.contact_id == self.mergee.id,
                Note.account_id == self.mergee.account_id,
            )
            .values(contact_id=self.base.id)
        )

    async def _merge_and_remove_mergee(self) -> None:
        """Deep-merge mergee → base then delete mergee.

        Chatwoot's semantics: ``mergee.deep_merge(base)`` — base keys
        win, mergee fills only the gaps. For JSONB blobs that means a
        recursive dict merge; for top-level scalars a simple "use base
        if present, otherwise mergee".
        """
        merged = self._compute_merged_attrs()

        # Apply merged attributes to base, then detach + delete mergee
        # so the destroy doesn't cascade-kill the base contact's rows we
        # just reassigned above.
        await self.session.refresh(self.mergee)
        await self.session.exec(
            delete(Contact).where(Contact.id == self.mergee.id)
        )

        for key, value in merged.items():
            setattr(self.base, key, value)
        self.session.add(self.base)
        await self.session.flush()

    def _compute_merged_attrs(self) -> dict[str, Any]:
        scalar_keys = ("identifier", "name", "email", "phone_number")
        out: dict[str, Any] = {}
        for key in scalar_keys:
            base_val = getattr(self.base, key)
            mergee_val = getattr(self.mergee, key)
            if _present(base_val):
                out[key] = base_val
            elif _present(mergee_val):
                out[key] = mergee_val
        out["additional_attributes"] = _deep_merge_base_wins(
            self.mergee.additional_attributes or {},
            self.base.additional_attributes or {},
        )
        out["custom_attributes"] = _deep_merge_base_wins(
            self.mergee.custom_attributes or {},
            self.base.custom_attributes or {},
        )
        return out


def _present(value: Any) -> bool:
    """Rails' ``present?`` — not nil, not empty string, not empty collection."""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, list | dict) and not value:
        return False
    return True


def _deep_merge_base_wins(mergee: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    """Ruby ``deep_merge`` semantics, with the second arg winning on collisions.

    Chatwoot's call is ``mergee.deep_merge(base)`` which reads "start
    with mergee, let base keys override". We mirror that exactly.
    """
    out = dict(mergee)
    for key, value in base.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge_base_wins(out[key], value)
        else:
            out[key] = value
    return out


# =========================================================================
# ContactIdentifyAction
# =========================================================================
@dataclass
class ContactIdentifyAction:
    """Merge-or-update by identifier / email / phone_number in that order.

    Ported from ``reference/chatwoot/app/actions/contact_identify_action.rb``.

    The priority tree is deliberately conservative: we won't merge two
    contacts if doing so would silently overwrite an ``identifier`` or
    an email that was already set with a different value. The lookup
    priority is **identifier → email → phone_number** and the merge
    priority matches.
    """

    session: AsyncSession
    contact: Contact
    params: dict[str, Any]
    retain_original_contact_name: bool = False
    _attributes_to_update: list[str] = field(
        default_factory=lambda: ["identifier", "name", "email", "phone_number"]
    )

    async def perform(self) -> Contact:
        params = normalize_contact_write(self.params)
        assert_valid_contact_identity(params)
        self.params = params  # mutate after normalization

        await self._merge_if_existing_by("identifier")
        await self._merge_if_existing_by("email")
        await self._merge_if_existing_by("phone_number", guard=self._phone_mergable)

        await self._update_contact()
        return self.contact

    async def _merge_if_existing_by(
        self,
        key: str,
        guard: Callable[[Contact], bool] | None = None,
    ) -> None:
        value = self.params.get(key)
        if not value:
            return
        stmt = select(Contact).where(
            Contact.account_id == self.contact.account_id,
            getattr(Contact, key) == value,
            Contact.id != self.contact.id,
        )
        match = (await self.session.exec(stmt)).first()
        if match is None:
            return
        # Guard: don't merge if doing so would change an identifier
        # that's already set to something else on the match.
        incoming_identifier = self.params.get("identifier")
        if (
            incoming_identifier
            and match.identifier
            and match.identifier != incoming_identifier
        ):
            self._attributes_to_update.remove(key)
            return
        if guard is not None and not guard(match):
            return

        merge = ContactMergeAction(
            session=self.session,
            account_id=self.contact.account_id,
            base=match,
            mergee=self.contact,
        )
        self.contact = await merge.perform()
        if self.retain_original_contact_name and "name" in self._attributes_to_update:
            self._attributes_to_update.remove("name")

    def _phone_mergable(self, match: Contact) -> bool:
        """Mirror ``mergable_phone_contact?`` — email trumps phone."""
        incoming_email = self.params.get("email")
        if not incoming_email:
            return True
        if match.email and match.email != incoming_email:
            if "phone_number" in self._attributes_to_update:
                self._attributes_to_update.remove("phone_number")
            return False
        return True

    async def _update_contact(self) -> None:
        updates: dict[str, Any] = {}
        for key in self._attributes_to_update:
            val = self.params.get(key)
            if _present(val):
                updates[key] = val

        incoming_custom = self.params.get("custom_attributes")
        if incoming_custom:
            updates["custom_attributes"] = _deep_merge_base_wins(
                self.contact.custom_attributes or {},
                incoming_custom,
            )
        incoming_additional = self.params.get("additional_attributes")
        if incoming_additional:
            updates["additional_attributes"] = _deep_merge_base_wins(
                self.contact.additional_attributes or {},
                incoming_additional,
            )

        if not updates:
            return
        for key, value in updates.items():
            setattr(self.contact, key, value)
        self.session.add(self.contact)
        await self.session.flush()


# =========================================================================
# Bulk write helpers used by the router
# =========================================================================
async def create_contact(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> Contact:
    data = normalize_contact_write(payload)
    assert_valid_contact_identity(data)
    contact = Contact(
        account_id=account_id,
        name=data.get("name") or "",
        email=data.get("email"),
        phone_number=data.get("phone_number"),
        identifier=data.get("identifier"),
        blocked=bool(data.get("blocked") or False),
        additional_attributes=data.get("additional_attributes") or {},
        custom_attributes=data.get("custom_attributes") or {},
    )
    session.add(contact)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise _uniqueness_422(e) from e
    # Rehydrate server-assigned timestamps + the ``contact_inboxes``
    # relationship so the presenter can render without lazy loads.
    await session.refresh(contact, attribute_names=["contact_inboxes"])
    return contact


async def update_contact(
    session: AsyncSession,
    *,
    contact: Contact,
    payload: dict[str, Any],
) -> Contact:
    data = normalize_contact_write(payload)
    assert_valid_contact_identity(data)

    scalar_keys = ("name", "email", "phone_number", "identifier", "blocked")
    for key in scalar_keys:
        if key in data:
            setattr(contact, key, data[key] if data[key] is not None else getattr(contact, key))
    # name is non-nullable-string in the ORM, guard against clobbering to None
    if contact.name is None:
        contact.name = ""
    if "additional_attributes" in data:
        contact.additional_attributes = _deep_merge_base_wins(
            contact.additional_attributes or {},
            data["additional_attributes"] or {},
        )
    if "custom_attributes" in data:
        contact.custom_attributes = _deep_merge_base_wins(
            contact.custom_attributes or {},
            data["custom_attributes"] or {},
        )

    session.add(contact)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise _uniqueness_422(e) from e
    await session.refresh(contact, attribute_names=["contact_inboxes"])
    return contact


def _uniqueness_422(exc: IntegrityError) -> ChatwootHTTPException:
    msg = str(getattr(exc, "orig", exc) or exc).lower()
    if "uniq_email_per_account" in msg:
        field_msg = "Email has already been taken"
    elif "uniq_identifier_per_account" in msg:
        field_msg = "Identifier has already been taken"
    elif "phone_number" in msg:
        field_msg = "Phone number has already been taken"
    else:
        field_msg = "Contact already exists"
    return ChatwootHTTPException(status_code=422, detail={"message": field_msg})


def company_name_expr():
    """The ``additional_attributes->>'company_name'`` text expression.

    Chatwoot has no Company model — an organisation is just the free-text
    ``company_name`` contact attribute, so both the companies aggregation
    and the ``?company=`` list filter key off this JSONB path.
    """
    return Contact.additional_attributes["company_name"].astext


async def list_companies(
    session: AsyncSession, *, account_id: int
) -> list[dict[str, Any]]:
    """Group the account's contacts by ``company_name`` (blanks ignored).

    Returns ``[{"name", "count"}, ...]`` ordered by count desc, then name —
    the "companies" view is a derived roll-up, not a stored entity.
    """
    name = company_name_expr()
    rows = (
        await session.exec(
            select(name.label("name"), func.count().label("count"))
            .where(
                Contact.account_id == account_id,
                name.isnot(None),
                name != "",
            )
            .group_by(name)
            .order_by(func.count().desc(), name.asc())
        )
    ).all()
    return [{"name": r[0], "count": int(r[1])} for r in rows]


__all__ = [
    "ContactIdentifyAction",
    "ContactInboxBuilder",
    "ContactMergeAction",
    "assert_valid_contact_identity",
    "company_name_expr",
    "create_contact",
    "list_companies",
    "normalize_contact_write",
    "update_contact",
]
