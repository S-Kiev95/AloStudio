#!/usr/bin/env bash
# Respaldo diario de AloStudio: base Postgres, archivos de MinIO y
# configuración, cifrado con restic y guardado fuera del servidor (bucket
# de Cloudflare R2). Guarda además los volcados de la base de los últimos
# días en el disco local, para restaurar rápido sin bajar nada.
#
# Configuración: ~/.config/alostudio-respaldo/env (ver env.ejemplo).
# Procedimiento completo y restauración: docs/operacion/respaldos.md.
#
# Uso: respaldar.sh            respaldo normal (cron diario)
#      respaldar.sh --sin-aviso  igual, sin avisar a Healthchecks (pruebas)

set -Eeuo pipefail
umask 077

CONF="${ALOSTUDIO_RESPALDO_ENV:-$HOME/.config/alostudio-respaldo/env}"
# shellcheck source=/dev/null
set -a
. "$CONF"
set +a

: "${RESTIC_REPOSITORY:?falta en $CONF}"
: "${RESTIC_PASSWORD_FILE:?falta en $CONF}"
: "${SERVIDOR:?falta en $CONF}"
: "${PG_CONTENEDOR:=alostudio-postgres}"
: "${PG_USUARIO:=alostudio}"
: "${PG_BASE:=alostudio}"
: "${MINIO_VOLUMEN:?falta en $CONF}"
: "${ARCHIVOS_CONFIG:=}"
: "${LOCAL_DIAS:=14}"
: "${HC_URL:=}"
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
export PATH="$HOME/bin:$PATH"

AVISAR=1
[ "${1:-}" = "--sin-aviso" ] && AVISAR=0

BASE_DIR="$HOME/respaldo"
ETAPA="$BASE_DIR/etapa"
LOCAL="$HOME/backups"
LOG="$BASE_DIR/respaldo.log"
mkdir -p "$BASE_DIR" "$LOCAL"
chmod 700 "$BASE_DIR" "$LOCAL"

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }

aviso() { # aviso <sufijo> [cuerpo]
  [ "$AVISAR" = 1 ] && [ -n "$HC_URL" ] || return 0
  curl -fsS -m 10 --retry 3 --data-raw "${2:-}" "$HC_URL$1" > /dev/null || true
}

falla() {
  log "FALLA: $*"
  aviso /fail "$(tail -n 20 "$LOG")"
  exit 1
}
trap 'falla "línea $LINENO: $BASH_COMMAND"' ERR

exec 9> "$BASE_DIR/.candado"
flock -n 9 || { log "FALLA: ya hay un respaldo corriendo"; exit 1; }

aviso /start
log "empieza ($SERVIDOR)"
rm -rf "$ETAPA"
mkdir -p "$ETAPA/config"

psql_prod() {
  docker exec "$PG_CONTENEDOR" psql -U "$PG_USUARIO" -d "$PG_BASE" -tA -c "$1"
}

# Conteos antes del volcado: el volcado tiene al menos estas filas. La
# prueba de restauración los compara con lo que restaura.
for t in accounts users contacts conversations messages; do
  printf '%s %s\n' "$t" "$(psql_prod "select count(*) from $t")"
done > "$ETAPA/conteos.txt"

docker exec "$PG_CONTENEDOR" pg_dump -U "$PG_USUARIO" -d "$PG_BASE" -Fc -Z 6 \
  > "$ETAPA/base.dump"
docker exec -i "$PG_CONTENEDOR" pg_restore --list < "$ETAPA/base.dump" > /dev/null
tam=$(stat -c %s "$ETAPA/base.dump")
[ "$tam" -gt 50000 ] || falla "el volcado pesa $tam bytes, demasiado poco para ser la base"
log "base: $tam bytes"

# MinIO: el volumen lo lee un contenedor (los archivos son de root) y sale
# como tar por la salida estándar, a nombre de este usuario.
docker run --rm -v "$MINIO_VOLUMEN":/data:ro alpine:3 tar -C /data -cf - . \
  > "$ETAPA/minio.tar"
archivos=$(tar -tf "$ETAPA/minio.tar" | grep -vc '/$' || true)
printf 'minio %s\n' "$archivos" >> "$ETAPA/conteos.txt"
log "minio: $archivos archivos"

for f in $ARCHIVOS_CONFIG; do
  [ -r "$f" ] || { log "aviso: no se puede leer $f"; continue; }
  destino="$ETAPA/config/$(printf '%s' "$f" | sed 's|^/||; s|/|__|g')"
  cp "$f" "$destino"
done
crontab -l > "$ETAPA/config/crontab" 2>/dev/null || true
cp -r "$HOME/.config/systemd/user" "$ETAPA/config/systemd-user" 2>/dev/null || true

restic backup --quiet --host "$SERVIDOR" --tag diario "$ETAPA"
log "copia externa hecha"

restic forget --quiet --host "$SERVIDOR" --prune \
  --keep-daily 7 --keep-weekly 4 --keep-monthly 12
log "retención aplicada (7 diarios, 4 semanales, 12 mensuales)"

# Los domingos, verificar el repositorio leyendo una parte de los datos.
if [ "$(date +%u)" = 7 ]; then
  restic check --quiet --read-data-subset=10%
  log "repositorio verificado"
fi

# Copia local de la base para restaurar rápido.
cp "$ETAPA/base.dump" "$LOCAL/alostudio-$(date +%F).dump"
find "$LOCAL" -maxdepth 1 -name 'alostudio-*.dump' -mtime +"$LOCAL_DIAS" -delete

rm -rf "$ETAPA"
log "termina bien"
aviso "" "$(tail -n 8 "$LOG")"
