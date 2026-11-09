#!/usr/bin/env bash
# Instala restic y rclone en ~/bin (sin sudo), con versión fija y checksum
# verificado contra el SHA256SUMS oficial de cada proyecto. Idempotente.

set -Eeuo pipefail

RESTIC_VERSION=0.19.1
RCLONE_VERSION=1.75.2

BIN="$HOME/bin"
mkdir -p "$BIN"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

if ! "$BIN/restic" version 2>/dev/null | grep -q "restic $RESTIC_VERSION "; then
  base="https://github.com/restic/restic/releases/download/v$RESTIC_VERSION"
  archivo="restic_${RESTIC_VERSION}_linux_amd64.bz2"
  curl -fsSL -o "$tmp/$archivo" "$base/$archivo"
  curl -fsSL -o "$tmp/SHA256SUMS" "$base/SHA256SUMS"
  (cd "$tmp" && grep " $archivo\$" SHA256SUMS | sha256sum -c -)
  bunzip2 -c "$tmp/$archivo" > "$BIN/restic"
  chmod 755 "$BIN/restic"
fi
"$BIN/restic" version

if ! "$BIN/rclone" version 2>/dev/null | grep -q "rclone v$RCLONE_VERSION\$"; then
  base="https://downloads.rclone.org/v$RCLONE_VERSION"
  archivo="rclone-v${RCLONE_VERSION}-linux-amd64.zip"
  curl -fsSL -o "$tmp/$archivo" "$base/$archivo"
  curl -fsSL -o "$tmp/SHA256SUMS" "$base/SHA256SUMS"
  (cd "$tmp" && grep " $archivo\$" SHA256SUMS | sha256sum -c -)
  # Sin depender de unzip (no siempre está y no hay sudo).
  python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' \
    "$tmp/$archivo" "$tmp"
  install -m 755 "$tmp/rclone-v${RCLONE_VERSION}-linux-amd64/rclone" "$BIN/rclone"
fi
"$BIN/rclone" version | head -n 1

mkdir -p "$HOME/.config/alostudio-respaldo"
chmod 700 "$HOME/.config/alostudio-respaldo"
echo "Listo. Siguiente paso: docs/operacion/respaldos.md, sección Puesta en marcha."
