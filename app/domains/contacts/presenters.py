"""Wire-shape renderers for Contact, ContactInbox, Note.

Every function here has a Ruby jbuilder counterpart; the top docstring
of each lists the exact file so a drift is one grep away.

Chatwoot's jbuilder emits integer unix timestamps for ``created_at`` /
``last_activity_at`` (via ``.to_i``). We preserve that rather than
ISO-8601 because it's the wire contract the Chatwoot frontend reads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import inspect as sa_inspect

from app.domains.contacts.models import Contact, ContactInbox, Note
from app.domains.inboxes.models import Inbox
from app.domains.users.models import AccountUser, User


def _unix(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    return int(dt.timestamp())


# ---- _inbox_slim.json.jbuilder --------------------------------------
def _present_inbox_slim(inbox: Inbox) -> dict[str, Any]:
    """Mirrors ``app/views/api/v1/models/_inbox_slim.json.jbuilder``."""
    # ``provider`` reads from ``inbox.channel.provider``. Only Channel::Api
    # ships in Phase 2; the API channel has no ``provider`` attribute, so
    # we emit ``None`` — same as Rails when ``.try(:provider)`` returns nil.
    return {
        "id": inbox.id,
        "avatar_url": "",  # Avatarable concern; deferred until Phase 6+
        "channel_id": inbox.channel_id,
        "name": inbox.name,
        "channel_type": inbox.channel_type,
        "provider": None,
    }


# ---- _contact_inbox.json.jbuilder -----------------------------------
def present_contact_inbox(row: ContactInbox) -> dict[str, Any]:
    return {
        "source_id": row.source_id,
        "inbox": _present_inbox_slim(row.inbox),
    }


# ---- _contact.json.jbuilder -----------------------------------------
def present_contact(
    contact: Contact,
    *,
    with_contact_inboxes: bool = False,
) -> dict[str, Any]:
    """Serialize a contact.

    Wire parity with ``app/views/api/v1/models/_contact.json.jbuilder``.
    The ``availability_status`` and ``thumbnail`` keys are emitted
    unconditionally — Chatwoot reads them from the ``AvailabilityStatusable``
    and ``Avatarable`` concerns which always return a string (``"offline"``
    or ``"online"`` / avatar URL or Gravatar fallback). We emit the
    ``"offline"`` + empty-string defaults until those concerns land in
    a later phase.
    """
    body: dict[str, Any] = {
        "additional_attributes": contact.additional_attributes or {},
        "availability_status": "offline",
        "email": contact.email,
        "id": contact.id,
        "name": contact.name,
        "phone_number": contact.phone_number,
        "blocked": contact.blocked,
        "identifier": contact.identifier,
        "thumbnail": "",
        "custom_attributes": contact.custom_attributes or {},
    }
    if contact.last_activity_at is not None:
        body["last_activity_at"] = _unix(contact.last_activity_at)
    if contact.created_at is not None:
        body["created_at"] = _unix(contact.created_at)
    if with_contact_inboxes:
        body["contact_inboxes"] = [
            present_contact_inbox(ci) for ci in _safe_contact_inboxes(contact)
        ]
    return body


def _safe_contact_inboxes(contact: Contact) -> list[ContactInbox]:
    """Return ``contact.contact_inboxes`` without triggering lazy load.

    After ``session.add + flush``, SQLAlchemy marks a freshly-created
    instance's relationships as unloaded. Touching the attribute from
    a sync context (like this presenter) raises ``MissingGreenlet``.
    We inspect the instance state and return an empty list when the
    collection hasn't been loaded — which is the correct value for a
    just-created contact since it has zero ContactInbox rows anyway.

    For contacts fetched via a query (``selectin`` eager-load configured
    on the relationship), the collection IS loaded, so this falls through
    to the real list.
    """
    state = sa_inspect(contact)
    if "contact_inboxes" in state.unloaded:
        return []
    return list(contact.contact_inboxes or [])


# ---- contacts/index.json.jbuilder -----------------------------------
def present_contacts_index(
    contacts: list[Contact],
    *,
    count: int,
    current_page: int,
    with_contact_inboxes: bool = True,
) -> dict[str, Any]:
    return {
        "meta": {"count": count, "current_page": current_page},
        "payload": [
            present_contact(c, with_contact_inboxes=with_contact_inboxes) for c in contacts
        ],
    }


# ---- contacts/search.json.jbuilder ----------------------------------
def present_contacts_search(
    contacts: list[Contact],
    *,
    count: int,
    current_page: int,
    has_more: bool,
    with_contact_inboxes: bool = True,
) -> dict[str, Any]:
    return {
        "meta": {
            "count": count,
            "current_page": current_page,
            "has_more": has_more,
        },
        "payload": [
            present_contact(c, with_contact_inboxes=with_contact_inboxes) for c in contacts
        ],
    }


# ---- contacts/show.json.jbuilder ------------------------------------
def present_contact_show(
    contact: Contact,
    *,
    with_contact_inboxes: bool = True,
) -> dict[str, Any]:
    return {
        "payload": present_contact(contact, with_contact_inboxes=with_contact_inboxes)
    }


# ---- contacts/create.json.jbuilder ----------------------------------
def present_contact_create(
    contact: Contact,
    contact_inbox: ContactInbox | None,
) -> dict[str, Any]:
    inbox_block: dict[str, Any] = {"inbox": None, "source_id": None}
    if contact_inbox is not None:
        inbox_block = {
            "inbox": _present_inbox_slim(contact_inbox.inbox),
            "source_id": contact_inbox.source_id,
        }
    return {
        "payload": {
            "contact": present_contact(contact, with_contact_inboxes=True),
            "contact_inbox": inbox_block,
        }
    }


# ---- _note.json.jbuilder --------------------------------------------
def _present_note_agent(
    user: User,
    *,
    account_id: int,
    account_user: AccountUser | None,
) -> dict[str, Any]:
    """Render the ``user`` block nested under a Note.

    Mirrors ``app/views/api/v1/models/_agent.json.jbuilder`` — in the
    note context Chatwoot calls the partial with ``resource: note.user``
    and ``Current.account`` already set to the caller's account. The
    ``availability_status`` / ``auto_offline`` fields come from the
    caller's :class:`AccountUser` row for that account (via the
    ``AvailabilityStatusable`` concern), so we thread it in explicitly.

    We reuse :func:`app.domains.inboxes.presenters.present_agent` to
    keep one canonical agent shape. The local import avoids a
    package-level dep on inboxes.
    """
    from app.domains.inboxes.presenters import present_agent

    return present_agent(
        account_id=account_id,
        account_user_availability=(
            account_user.availability if account_user is not None else None
        ),
        account_user_auto_offline=(
            account_user.auto_offline if account_user is not None else None
        ),
        user=user,
    )


def present_note(
    note: Note,
    *,
    account_user: AccountUser | None = None,
) -> dict[str, Any]:
    """Serialize a note.

    ``account_user`` is the :class:`AccountUser` for
    ``(note.user_id, note.account_id)``. Pass ``None`` when the note
    has no user (pure system note); when the note *has* a user but no
    matching AccountUser row (e.g. user removed from account) we still
    emit the agent block with defaults — same as Rails' safe-nav path.
    """
    body: dict[str, Any] = {
        "id": note.id,
        "content": note.content,
        # ! Bug-for-bug parity with Chatwoot: ``_note.json.jbuilder``
        # does ``json.account_id json.account_id`` which serializes as
        # ``null`` (reads the unset builder attribute). Same for
        # ``contact_id``. Not a typo here — check the source if you
        # doubt it. Chatwoot v4.13.0 line-for-line.
        "account_id": None,
        "contact_id": None,
        "created_at": _unix(note.created_at),
        "updated_at": _unix(note.updated_at),
    }
    if note.user is not None:
        body["user"] = _present_note_agent(
            note.user,
            account_id=note.account_id,
            account_user=account_user,
        )
    return body


def present_notes_index(
    notes: list[Note],
    *,
    account_users_by_user_id: dict[int, AccountUser] | None = None,
) -> list[dict[str, Any]]:
    """Top-level JSON array — matches ``notes/index.json.jbuilder``.

    ``account_users_by_user_id`` is a caller-batched lookup keyed by
    ``user_id`` for the note's account, so the presenter stays N+1-free.
    """
    lookup = account_users_by_user_id or {}
    return [
        present_note(
            n,
            account_user=lookup.get(n.user_id) if n.user_id is not None else None,
        )
        for n in notes
    ]


__all__ = [
    "present_contact",
    "present_contact_create",
    "present_contact_inbox",
    "present_contact_show",
    "present_contacts_index",
    "present_contacts_search",
    "present_note",
    "present_notes_index",
]
