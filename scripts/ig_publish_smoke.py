"""Real-Meta smoke test for the Instagram publish path (manual, NOT pytest).

Reads ``PAGE_TOKEN`` + ``INSTAGRAM_BUSINESS_ACCOUNT_ID`` (and optional
``IG_SMOKE_IMAGE_URL`` / ``IG_SMOKE_CAPTION``) from ``.env.local`` and runs
a REAL publish against Meta's Graph API using the very same
``app.domains.instagram.publisher`` + ``poller`` code the app uses.

It prints **masked** diagnostics — the access token is never echoed.

Usage::

    .venv/Scripts/python.exe scripts/ig_publish_smoke.py
    # optional cleanup (delete the just-published media afterwards):
    IG_SMOKE_CLEANUP=1 .venv/Scripts/python.exe scripts/ig_publish_smoke.py

NOTE: this posts a real image to the linked Instagram account. Use a test
account. Delete with the dashboard DELETE endpoint or IG_SMOKE_CLEANUP=1.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

# Make ``app`` importable when run as ``python scripts/ig_publish_smoke.py``
# (the repo root is this file's parent's parent).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows consoles default to cp1252 — force UTF-8 so status glyphs print.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

from dotenv import dotenv_values


def _load() -> dict[str, str]:
    vals: dict[str, str] = {}
    vals.update({k: v for k, v in dotenv_values(".env").items() if v is not None})
    vals.update(
        {k: v for k, v in dotenv_values(".env.local").items() if v is not None}
    )
    # Real process env wins (lets you override on the command line).
    for k in (
        "PAGE_TOKEN",
        "INSTAGRAM_BUSINESS_ACCOUNT_ID",
        "IG_SMOKE_IMAGE_URL",
        "IG_SMOKE_CAPTION",
        "IG_SMOKE_CLEANUP",
        "IG_SMOKE_DELETE_MEDIA_ID",
        "META_GRAPH_API_VERSION",
    ):
        if os.environ.get(k):
            vals[k] = os.environ[k]
    return vals


def _mask(tok: str) -> str:
    if not tok:
        return "(missing)"
    return f"set (len={len(tok)}, starts={tok[:4]}…)"


async def main() -> int:
    cfg = _load()
    page_token = cfg.get("PAGE_TOKEN") or ""
    ig_id = cfg.get("INSTAGRAM_BUSINESS_ACCOUNT_ID") or ""
    image_url = (
        cfg.get("IG_SMOKE_IMAGE_URL")
        or "https://picsum.photos/seed/alostudio/1080/1080.jpg"
    )
    caption = cfg.get("IG_SMOKE_CAPTION") or "AloStudio smoke test"
    version = cfg.get("META_GRAPH_API_VERSION") or "v23.0"
    cleanup = (cfg.get("IG_SMOKE_CLEANUP") or "") in ("1", "true", "True")

    # The publisher reads the version via get_settings(); make sure the
    # process env carries it before that import resolves settings.
    os.environ["META_GRAPH_API_VERSION"] = version

    print("=== Instagram publish smoke test (REAL Meta call) ===")
    print(f"PAGE_TOKEN:               {_mask(page_token)}")
    print(f"IG_BUSINESS_ACCOUNT_ID:   {ig_id or '(missing)'}")
    print(f"image_url:                {image_url}")
    print(f"caption:                  {caption!r}")
    print(f"graph version:            {version}")
    print(f"cleanup after:            {cleanup}")
    print()

    if not page_token or not ig_id:
        print(
            "MISSING credentials — set PAGE_TOKEN and "
            "INSTAGRAM_BUSINESS_ACCOUNT_ID in .env.local."
        )
        return 2

    from app.domains.instagram import poller, publisher

    channel = SimpleNamespace(
        id=0, account_id=0, instagram_id=ig_id, access_token=page_token
    )

    # Delete-only mode: validate the I.6 delete path on an existing media
    # id (also handy to clean up earlier smoke posts).
    delete_only = cfg.get("IG_SMOKE_DELETE_MEDIA_ID")
    if delete_only:
        d = await publisher.delete_media(channel, ig_media_id=delete_only)
        print(
            f"[delete]    media_id={delete_only} ok={d.ok} "
            f"err={d.error_code}: {d.error_message}"
        )
        if d.ok:
            print("\nDELETE OK")
            return 0
        print("\nDELETE FAILED")
        return 1

    # 0) Quota (informational).
    quota = await publisher.fetch_publishing_limit(channel)
    if quota.ok:
        print(
            f"[quota]     usage={quota.quota_usage}/{quota.quota_total} "
            f"(exceeded={quota.exceeded})"
        )
    else:
        print(
            f"[quota]     check failed (non-fatal): "
            f"{quota.error_code}: {quota.error_message}"
        )

    # 1) Create container.
    params = publisher.build_image_container_params(
        image_url=image_url, caption=caption
    )
    c = await publisher.create_container(channel, params=params)
    print(
        f"[create]    ok={c.ok} container_id={c.container_id} "
        f"err={c.error_code}: {c.error_message}"
    )
    if not c.ok or c.container_id is None:
        print("\nFAIL at container create.")
        return 1

    # 2) Poll to FINISHED (images are usually instant).
    st = await poller.poll_until_terminal(
        channel,
        container_id=c.container_id,
        interval_seconds=4,
        max_attempts=15,
    )
    print(f"[poll]      status={st.status_code} err={st.error}")
    if st.status_code != "FINISHED":
        print("\nFAIL at poll.")
        return 1

    # 3) Publish.
    p = await publisher.publish_container(channel, creation_id=c.container_id)
    print(
        f"[publish]   ok={p.ok} media_id={p.ig_media_id} "
        f"err={p.error_code}: {p.error_message}"
    )
    if not p.ok or p.ig_media_id is None:
        print("\nFAIL at publish.")
        return 1

    # 4) Permalink.
    link = await publisher.fetch_permalink(channel, ig_media_id=p.ig_media_id)
    print(f"[permalink] {link}")

    # 5) Optional cleanup.
    if cleanup:
        d = await publisher.delete_media(channel, ig_media_id=p.ig_media_id)
        print(f"[cleanup]   delete ok={d.ok} err={d.error_code}: {d.error_message}")

    print(f"\n✅ SMOKE TEST PASSED — published media id: {p.ig_media_id}")
    if link:
        print(f"   View it: {link}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
