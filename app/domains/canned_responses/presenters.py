"""Wire-shape presenter for CannedResponse.

Chatwoot's controller renders the model with a bare ``render json:``
(no jbuilder view, no ``payload`` envelope): the collection is a plain
array and a single resource is a plain object. We emit the fields the
dashboard consumes — id / short_code / content / account_id — and omit
the timestamps (nothing reads them), matching the lean presenters used
by the labels + macros domains.
"""

from __future__ import annotations

from typing import Any

from app.domains.canned_responses.models import CannedResponse


def present_canned_response(cr: CannedResponse) -> dict[str, Any]:
    return {
        "id": cr.id,
        "short_code": cr.short_code,
        "content": cr.content,
        "account_id": cr.account_id,
    }


def present_canned_responses(
    rows: list[CannedResponse],
) -> list[dict[str, Any]]:
    """``GET /canned_responses`` → bare array (no envelope)."""
    return [present_canned_response(cr) for cr in rows]


__all__ = ["present_canned_response", "present_canned_responses"]
