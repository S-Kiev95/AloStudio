"""Request bodies for the contacts + notes + contact_inboxes + contact_merge endpoints.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/contacts_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/contacts/notes_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/contacts/contact_inboxes_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/actions/contact_merges_controller.rb

Notes on Rails-isms we preserve:

* ``permit(...)`` silently drops unknown keys — we mirror that with
  ``extra='ignore'`` instead of raising a 422 on surplus fields.
* ``params.require(:note)`` / ``params.require(:custom_attribute_definition)``
  means the endpoint expects a top-level object envelope. We use a
  dedicated wrapper model (``NoteEnvelope`` etc.) so the FastAPI
  request shape matches Rails byte-for-byte.
* Values pass through untouched (``additional_attributes: {}`` allows
  *any* nested dict because Rails' ``attr: {}`` permit lets arbitrary
  JSON through at that key).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# POST /api/v1/accounts/:id/contacts
# ---------------------------------------------------------------------------
class ContactCreateRequest(BaseModel):
    """Flat body (no ``contact:`` wrapper — Chatwoot's permit is unwrapped).

    ``inbox_id`` + ``source_id`` are NOT in ``permitted_params`` but the
    controller still reads them at top level to optionally spawn a
    ``ContactInbox`` via ``build_contact_inbox``. We model them here so
    the router can thread them through.
    """

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    identifier: str | None = None
    email: str | None = None
    phone_number: str | None = None
    blocked: bool | None = None
    avatar_url: str | None = None  # accepted, deferred (Avatarable — Phase 6+)
    additional_attributes: dict[str, Any] | None = None
    custom_attributes: dict[str, Any] | None = None

    # Read from params but outside permitted_params — used by
    # ``build_contact_inbox`` to optionally attach a ContactInbox on create.
    inbox_id: int | None = None
    source_id: str | None = None


class ContactUpdateRequest(BaseModel):
    """Same allowlist as create, minus the contact_inbox ride-along keys.

    Chatwoot's ``contact_update_params`` merges the incoming
    ``custom_attributes`` / ``additional_attributes`` into the existing
    JSON blobs rather than replacing them — the service layer handles
    that; at the wire we accept the same shape.
    """

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    identifier: str | None = None
    email: str | None = None
    phone_number: str | None = None
    blocked: bool | None = None
    avatar_url: str | None = None
    additional_attributes: dict[str, Any] | None = None
    custom_attributes: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# POST /contacts/:id/destroy_custom_attributes
# ---------------------------------------------------------------------------
class DestroyCustomAttributesRequest(BaseModel):
    """Body for ``destroy_custom_attributes``.

    Chatwoot reads ``params[:custom_attributes]`` as an array of keys
    and does ``@contact.custom_attributes.excluding(keys)``.
    """

    model_config = ConfigDict(extra="ignore")

    custom_attributes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# POST / PATCH /contacts/:id/notes
# ---------------------------------------------------------------------------
class _NoteBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str = Field(min_length=1)


class NoteEnvelope(BaseModel):
    """Wrapper matching ``params.require(:note)``.

    Chatwoot expects ``{"note": {"content": "..."}}`` — any other shape
    400s. We model the envelope explicitly so the 422 message comes out
    of Pydantic at the right nesting depth.
    """

    model_config = ConfigDict(extra="ignore")

    note: _NoteBody


# ---------------------------------------------------------------------------
# POST /contacts/:id/contact_inboxes
# ---------------------------------------------------------------------------
class ContactInboxCreateRequest(BaseModel):
    """Body for ``ContactInboxesController#create``.

    ``inbox_id`` is read from the JSON body (not the URL — the nested
    resource uses the CONTACT id in the path and the inbox id in the
    body). ``source_id`` is optional — the builder generates a UUID for
    API channels when it's missing.
    """

    model_config = ConfigDict(extra="ignore")

    inbox_id: int
    source_id: str | None = None


# ---------------------------------------------------------------------------
# POST /actions/contact_merge
# ---------------------------------------------------------------------------
class ContactMergeRequest(BaseModel):
    """Body for ``Actions::ContactMergesController#create``.

    Flat body — Chatwoot reads both keys off the root params, no wrapper.
    """

    model_config = ConfigDict(extra="ignore")

    base_contact_id: int
    mergee_contact_id: int


__all__ = [
    "ContactCreateRequest",
    "ContactInboxCreateRequest",
    "ContactMergeRequest",
    "ContactUpdateRequest",
    "DestroyCustomAttributesRequest",
    "NoteEnvelope",
]
