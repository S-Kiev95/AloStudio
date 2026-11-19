#!/usr/bin/env bash
# The local model behind the help assistant (Ayuda), as a Docker container.
#
#   bash ops/llm/levantar.sh            # Qwen3 4B Instruct, the one evaluated
#
# Then set LOCAL_LLM_URL=http://127.0.0.1:8092 in Ajustes → Instalación.
# It uses 4 CPUs and about 4.5 GB of RAM; the help is read once (about 3
# minutes) and kept, and the worker re-reads it every 5 minutes if needed.
# Measurements: ops/llm/README.md.
set -euo pipefail

MODELS="${MODELS:-$HOME/llm/models}"
REPO="unsloth/Qwen3-4B-Instruct-2507-GGUF"
FILE="Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
# The llama.cpp build that was evaluated (build 12464, commit d3c3e242c).
IMAGE="ghcr.io/ggml-org/llama.cpp@sha256:5b43086e3ba7ea5794d72904654f6cd41224a9b1c6ac0398f4940ee380d30f23"

mkdir -p "$MODELS"
if [ ! -s "$MODELS/$FILE" ]; then
  echo "Bajando $FILE (2,5 GB)…"
  curl -fL --retry 3 -o "$MODELS/$FILE.part" "https://huggingface.co/$REPO/resolve/main/$FILE"
  mv "$MODELS/$FILE.part" "$MODELS/$FILE"
fi

docker rm -f alostudio-llm >/dev/null 2>&1 || true
docker run -d --name alostudio-llm --restart unless-stopped --cpus=4 \
  -p 127.0.0.1:8092:8080 -v "$MODELS":/models:ro "$IMAGE" \
  -m "/models/$FILE" -t 4 -c 8192 -np 1 --jinja >/dev/null

for _ in $(seq 1 90); do
  if curl -sf http://127.0.0.1:8092/health >/dev/null; then
    echo "Listo en http://127.0.0.1:8092 — poné LOCAL_LLM_URL en Ajustes → Instalación."
    exit 0
  fi
  sleep 2
done
echo "El modelo no respondió; mirá: docker logs alostudio-llm" >&2
exit 1
