#!/usr/bin/env bash
# Instala el servicio local de embeddings (EmbeddingGemma 2, F9) en un
# servidor de AloStudio. Idempotente. Correr desde ~/AloStudio:
#   bash ops/embeddings/instalar.sh
# Después: agregar EMBEDDINGS_SERVICE_URL=http://127.0.0.1:8100 al .env y
# reiniciar backend y worker (docs/operacion/embeddings.md).

set -Eeuo pipefail

cd "$(dirname "$0")/../.."
UV="${UV:-$HOME/.local/bin/uv}"

# Entorno aparte: torch no entra al .venv de la app.
[ -x .venv-embeddings/bin/python ] || "$UV" venv -q -p 3.12 .venv-embeddings
"$UV" pip install -q -p .venv-embeddings/bin/python \
  -r app/embeddings_service/requirements.txt \
  --index-url https://download.pytorch.org/whl/cpu \
  --extra-index-url https://pypi.org/simple \
  --index-strategy unsafe-best-match

mkdir -p "$HOME/.config/systemd/user" "$HOME/logs"
cp ops/embeddings/alostudio-embeddings.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now alostudio-embeddings
systemctl --user restart alostudio-embeddings

# El modelo tarda ~15 s en cargar (más la primera vez, que lo descarga).
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8100/health | grep -q '"ok":true'; then
    echo "Listo: servicio de embeddings arriba en 127.0.0.1:8100"
    exit 0
  fi
  sleep 5
done
echo "!! el servicio no respondió; ver ~/logs/embeddings.log" >&2
exit 1
