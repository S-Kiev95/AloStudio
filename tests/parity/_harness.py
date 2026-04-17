"""Parity test harness.

A parity test asserts that — given the same input — the AloStudio FastAPI
backend and the reference Chatwoot Rails backend produce equivalent outputs.
"Equivalent" means:

  * same HTTP status code
  * same response JSON after normalising volatile fields (timestamps, IDs,
    access tokens, pubsub tokens, etc.)

The harness is intentionally tolerant about structural drift: you pass
`ignore_paths` to allow known-different keys, and `id_aliases` to map
differently-numbered IDs between the two systems. Over time each domain's
parity test module accumulates these annotations — they become executable
documentation of "where the two backends intentionally differ".
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from deepdiff import DeepDiff  # type: ignore[import-untyped]

# Paths we always strip before comparing, regardless of endpoint.
ALWAYS_IGNORE: tuple[str, ...] = (
    r"root\['created_at'\]",
    r"root\['updated_at'\]",
    r"root\['confirmed_at'\]",
    r"root\['last_sign_in_at'\]",
    r"root\['pubsub_token'\]",
    r"root\['access_token'\]",
    r"root\['id'\]",
    r"root\['uid'\]",
    r"root\['sso_token'\]",
    # nested variants — add more here as we discover them
    r"root\[.*\]\['created_at'\]",
    r"root\[.*\]\['updated_at'\]",
    r"root\[.*\]\['id'\]",
)


def _compiled_ignore(extra: list[str] | None) -> list[re.Pattern[str]]:
    patterns = list(ALWAYS_IGNORE) + list(extra or [])
    return [re.compile(p) for p in patterns]


def assert_json_parity(
    alo_response: httpx.Response,
    cw_response: httpx.Response,
    *,
    ignore_paths: list[str] | None = None,
    ignore_order: bool = True,
) -> None:
    """Assert that the AloStudio and Chatwoot responses match.

    Args:
        alo_response: response from AloStudio's FastAPI app.
        cw_response:  response from the reference Chatwoot Rails app.
        ignore_paths: regex patterns (DeepDiff-style) to exclude in addition to
                      the common volatile fields.
        ignore_order: for list fields where order is semantically irrelevant.
    """
    assert alo_response.status_code == cw_response.status_code, (
        f"status mismatch: alo={alo_response.status_code} cw={cw_response.status_code}\n"
        f"alo body: {alo_response.text[:500]}\n"
        f"cw body:  {cw_response.text[:500]}"
    )
    alo_json = _safe_json(alo_response)
    cw_json = _safe_json(cw_response)

    diff = DeepDiff(
        cw_json,
        alo_json,
        ignore_order=ignore_order,
        exclude_regex_paths=_compiled_ignore(ignore_paths),
    )
    assert not diff, f"JSON parity diff:\n{diff.pretty()}"


def _safe_json(r: httpx.Response) -> Any:
    ctype = r.headers.get("content-type", "")
    if "application/json" not in ctype:
        return {"__raw__": r.text}
    try:
        return r.json()
    except ValueError:
        return {"__raw__": r.text}
