"""JSON shape for media library assets."""

from __future__ import annotations

from typing import Any

from app.domains.media_library.models import MediaAsset
from app.domains.media_library.service import asset_preview_url


def present_asset(asset: MediaAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "kind": asset.kind,
        "filename": asset.filename,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        # Short-lived, for previews only. Publications reference the asset by
        # ``id`` and get a fresh link when they go out.
        "url": asset_preview_url(asset),
        "uploaded_by_id": asset.uploaded_by_id,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


__all__ = ["present_asset"]
