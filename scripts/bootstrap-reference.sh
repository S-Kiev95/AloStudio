#!/usr/bin/env bash
# Clone the Chatwoot reference that parity tests compare against.
# Pinned to the stable tag used by this branch; bump CHATWOOT_REF_VERSION when
# you intentionally want to track a newer upstream release.
set -euo pipefail

CHATWOOT_REF_VERSION="${CHATWOOT_REF_VERSION:-v4.13.0}"
TARGET="${1:-reference/chatwoot}"

if [[ -d "$TARGET/.git" ]]; then
    echo "[bootstrap-reference] $TARGET already exists — skipping clone."
    exit 0
fi

mkdir -p "$(dirname "$TARGET")"
git clone --depth 1 --branch "$CHATWOOT_REF_VERSION" \
    https://github.com/chatwoot/chatwoot.git "$TARGET"

echo "[bootstrap-reference] cloned $CHATWOOT_REF_VERSION into $TARGET"
