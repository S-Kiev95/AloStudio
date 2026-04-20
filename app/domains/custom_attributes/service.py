"""CustomAttributeDefinition write helpers.

Ported from:
  reference/chatwoot/app/models/custom_attribute_definition.rb
  reference/chatwoot/app/controllers/api/v1/accounts/custom_attribute_definitions_controller.rb

The model does three validations we enforce here:
  * ``attribute_display_name`` presence
  * ``attribute_key`` format  ``/\\A[\\p{L}\\p{N}_.\\-]+\\z/``
  * ``attribute_key`` must not shadow a built-in Contact/Conversation field
    (Chatwoot's ``STANDARD_ATTRIBUTES`` guard).

Ruby's ``\\p{L}\\p{N}`` classes cover unicode letters + numbers. Python's
``re`` with the ``UNICODE`` flag (default in py3) already does the same
for ``\\w`` minus underscore — so we spell the class explicitly here to
match Chatwoot byte-for-byte.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.custom_attributes.models import (
    STANDARD_ATTRIBUTE_KEYS,
    CustomAttributeDefinition,
    attr_model_from_str,
    display_type_from_str,
)

# Unicode letters/digits/underscore (``\w``) plus ``.`` and ``-`` — mirrors
# Ruby's ``/\A[\p{L}\p{N}_.\-]+\z/`` with ``re.UNICODE`` (default in py3).
_KEY_RE = re.compile(r"^[\w.\-]+\Z", re.UNICODE)


def _assert_valid_key(key: str) -> None:
    if not key or not _KEY_RE.match(key):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Attribute key must be alphanumeric, dots, dashes or underscores"},
        )


def _assert_no_conflict(attribute_key: str, attribute_model_str: str) -> None:
    forbidden = STANDARD_ATTRIBUTE_KEYS.get(attribute_model_str, frozenset())
    if attribute_key in forbidden:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "Attribute key is reserved and cannot be used as a custom attribute"
            },
        )


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip strings + coerce enum strings to integers for write."""
    out = dict(payload)
    if "attribute_key" in out and isinstance(out["attribute_key"], str):
        out["attribute_key"] = out["attribute_key"].strip()
    if "attribute_display_name" in out and isinstance(out["attribute_display_name"], str):
        out["attribute_display_name"] = out["attribute_display_name"].strip()
    if "attribute_model" in out and isinstance(out["attribute_model"], str):
        out["attribute_model"] = attr_model_from_str(out["attribute_model"])
    if "attribute_display_type" in out and isinstance(out["attribute_display_type"], str):
        out["attribute_display_type"] = display_type_from_str(out["attribute_display_type"])
    return out


async def create_definition(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> CustomAttributeDefinition:
    data = _normalize(payload)
    key = data.get("attribute_key")
    if not data.get("attribute_display_name"):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Attribute display name can't be blank"},
        )
    if not key:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Attribute key can't be blank"}
        )
    _assert_valid_key(key)
    # The conflict guard uses the STRING form of attribute_model.
    model_int = int(
        data.get("attribute_model", 0)
    )  # default conversation_attribute → 0
    from app.domains.custom_attributes.models import attr_model_to_str

    _assert_no_conflict(key, attr_model_to_str(model_int))

    definition = CustomAttributeDefinition(
        account_id=account_id,
        attribute_display_name=data["attribute_display_name"],
        attribute_key=key,
        attribute_description=data.get("attribute_description"),
        attribute_display_type=int(data.get("attribute_display_type", 0)),
        attribute_model=model_int,
        attribute_values=data.get("attribute_values") or [],
        regex_pattern=data.get("regex_pattern"),
        regex_cue=data.get("regex_cue"),
    )
    session.add(definition)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Attribute key has already been taken for this model"},
        ) from e
    # Rehydrate timestamps (``onupdate=func.now()`` expires ``updated_at``
    # after flush; the presenter reads both so we need them loaded).
    await session.refresh(definition)
    return definition


async def update_definition(
    session: AsyncSession,
    *,
    definition: CustomAttributeDefinition,
    payload: dict[str, Any],
) -> CustomAttributeDefinition:
    data = _normalize(payload)
    scalar_keys = (
        "attribute_display_name",
        "attribute_description",
        "attribute_display_type",
        "attribute_model",
        "regex_pattern",
        "regex_cue",
    )
    for key in scalar_keys:
        if key in data:
            setattr(definition, key, data[key])
    if "attribute_values" in data and data["attribute_values"] is not None:
        definition.attribute_values = data["attribute_values"]
    # ``attribute_key`` is intentionally NOT updatable — Chatwoot
    # permits it in the payload but in practice updating the key breaks
    # every row that stored values under the old key. Match the Rails
    # behaviour of "accept but silently skip if changed" to keep the
    # wire contract identical.
    session.add(definition)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Attribute key has already been taken for this model"},
        ) from e
    await session.refresh(definition)
    return definition


__all__ = ["create_definition", "update_definition"]
