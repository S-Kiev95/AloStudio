#!/usr/bin/env bash
# Prueba mensual de restauración: baja la última copia externa, restaura la
# base en un Postgres temporal (sin puertos publicados, se borra al final),
# abre el tar de MinIO y compara con los conteos guardados al respaldar.
# Un respaldo que nunca se restauró no cuenta.
#
# Uso: probar-restauracion.sh            (cron mensual)
#      probar-restauracion.sh --sin-aviso

set -Eeuo pipefail
umask 077

CONF="${ALOSTUDIO_RESPALDO_ENV:-$HOME/.config/alostudio-respaldo/env}"
# shellcheck source=/dev/null
. "$CONF"

: "${RESTIC_REPOSITORY:?falta en $CONF}"
: "${RESTIC_PASSWORD_FILE:?falta en $CONF}"
: "${SERVIDOR:?falta en $CONF}"
: "${PG_IMAGEN:=pgvector/pgvector:pg16}"
: "${HC_URL_PRUEBA:=}"
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
export PATH="$HOME/bin:$PATH"

AVISAR=1
[ "${1:-}" = "--sin-aviso" ] && AVISAR=0

BASE_DIR="$HOME/respaldo"
LOG="$BASE_DIR/respaldo.log"
mkdir -p "$BASE_DIR"
PRUEBA=$(mktemp -d "$BASE_DIR/prueba.XXXXXX")
CONT="alostudio-prueba-restauracion"

log() { printf '%s %s\n' "$(date '+%F %T')" "prueba: $*" >> "$LOG"; }

aviso() {
  [ "$AVISAR" = 1 ] && [ -n "$HC_URL_PRUEBA" ] || return 0
  curl -fsS -m 10 --retry 3 --data-raw "${2:-}" "$HC_URL_PRUEBA$1" > /dev/null || true
}

limpiar() {
  docker rm -f "$CONT" > /dev/null 2>&1 || true
  rm -rf "$PRUEBA"
}

falla() {
  log "FALLA: $*"
  aviso /fail "$(tail -n 20 "$LOG")"
  limpiar
  exit 1
}
trap 'falla "línea $LINENO: $BASH_COMMAND"' ERR

aviso /start
log "empieza ($SERVIDOR)"

restic restore latest --quiet --host "$SERVIDOR" --target "$PRUEBA"
ETAPA=$(find "$PRUEBA" -type d -name etapa | head -n 1)
[ -n "$ETAPA" ] && [ -f "$ETAPA/base.dump" ] || falla "la copia no trae base.dump"
fecha=$(restic snapshots latest --host "$SERVIDOR" --json | grep -o '"time":"[^"]*' | head -n 1 | cut -d'"' -f4)
log "copia del $fecha bajada"

docker run -d --name "$CONT" --network none \
  -e POSTGRES_PASSWORD="$(head -c 18 /dev/urandom | base64)" \
  -e POSTGRES_USER=prueba -e POSTGRES_DB=prueba \
  "$PG_IMAGEN" > /dev/null
for _ in $(seq 1 60); do
  docker exec "$CONT" pg_isready -U prueba -d prueba > /dev/null 2>&1 && break
  sleep 1
done
docker exec "$CONT" pg_isready -U prueba -d prueba > /dev/null

docker exec -i "$CONT" pg_restore -U prueba -d prueba --no-owner --no-acl \
  < "$ETAPA/base.dump"
log "base restaurada"

problemas=0
while read -r tabla esperado; do
  if [ "$tabla" = minio ]; then
    real=$(tar -tf "$ETAPA/minio.tar" | grep -vc '/$' || true)
  else
    real=$(docker exec "$CONT" psql -U prueba -d prueba -tA -c "select count(*) from $tabla")
  fi
  if [ "$real" -lt "$esperado" ]; then
    log "$tabla: $real filas, se esperaban al menos $esperado"
    problemas=$((problemas + 1))
  else
    log "$tabla: $real (esperado ≥ $esperado)"
  fi
done < "$ETAPA/conteos.txt"

[ "$problemas" = 0 ] || falla "$problemas conteos no coinciden"

limpiar
log "termina bien"
aviso "" "$(tail -n 10 "$LOG")"
