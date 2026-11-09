#!/usr/bin/env bash
# Puesta en marcha guiada de los respaldos en un servidor. La corre el dueño
# en su terminal, así los secretos no pasan por ningún chat:
#
#   ssh -t <usuario>@<servidor> bash AloStudio/ops/respaldo/configurar.sh
#
# Las copias van a un bucket de Cloudflare R2 (compatible con S3). Antes hay
# que crear el bucket y un token de API de R2 con permiso de lectura y
# escritura solo sobre ese bucket (docs/operacion/respaldos.md).

set -Eeuo pipefail
umask 077
export PATH="$HOME/bin:$PATH"

DIR="$HOME/.config/alostudio-respaldo"
ENV="$DIR/env"
CLAVE="$DIR/clave"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DIR"
chmod 700 "$DIR"

command -v restic > /dev/null || {
  echo "Falta restic: corré primero $REPO_DIR/instalar.sh"
  exit 1
}

echo "== 1. Nombre de este servidor (ctc, develop, ...)"
read -r -p "Servidor: " SERVIDOR
[ -n "$SERVIDOR" ] || { echo "Hace falta un nombre."; exit 1; }

echo
echo "== 2. Volumen de MinIO"
docker volume ls --format '{{.Name}}' | grep -i minio || true
read -r -p "Nombre del volumen (de la lista de arriba): " MINIO_VOLUMEN

echo
echo "== 3. Cloudflare R2"
read -r -p "ID de cuenta de Cloudflare (Account ID): " R2_CUENTA
read -r -p "Nombre del bucket [alostudio-respaldos]: " R2_BUCKET
R2_BUCKET=${R2_BUCKET:-alostudio-respaldos}
read -r -p "Access Key ID del token de R2: " R2_KEY_ID
read -r -s -p "Secret Access Key del token de R2 (no se ve al escribir): " R2_SECRET
echo
[ -n "$R2_CUENTA" ] && [ -n "$R2_KEY_ID" ] && [ -n "$R2_SECRET" ] || {
  echo "Faltan datos de R2."
  exit 1
}
REPO="s3:https://$R2_CUENTA.r2.cloudflarestorage.com/$R2_BUCKET/$SERVIDOR"

echo
echo "== 4. Clave de cifrado de las copias"
if [ -s "$CLAVE" ]; then
  echo "Ya hay una clave en $CLAVE, se usa esa (la que guardaste antes)."
else
  head -c 32 /dev/urandom | base64 | tr -d '\n' > "$CLAVE"
  chmod 600 "$CLAVE"
  echo
  echo "  CLAVE: $(cat "$CLAVE")"
  echo
  echo "  Guardala AHORA en tu gestor de contraseñas. Sin ella las copias no"
  echo "  se pueden abrir, y si se pierde el servidor se pierde con él."
  read -r -p "  Enter cuando la hayas guardado... " _
  clear
fi

echo
echo "== 5. Avisos de Healthchecks.io (pegá cada URL de ping, o Enter para omitir)"
read -r -p "URL del respaldo diario: " HC_URL
read -r -p "URL de la prueba mensual de restauración: " HC_URL_PRUEBA

cat > "$ENV" <<EOF
SERVIDOR=$SERVIDOR
RESTIC_REPOSITORY=$REPO
RESTIC_PASSWORD_FILE=$CLAVE
AWS_ACCESS_KEY_ID=$R2_KEY_ID
AWS_SECRET_ACCESS_KEY=$R2_SECRET
AWS_DEFAULT_REGION=auto
PG_CONTENEDOR=alostudio-postgres
PG_USUARIO=alostudio
PG_BASE=alostudio
MINIO_VOLUMEN=$MINIO_VOLUMEN
ARCHIVOS_CONFIG="\$HOME/AloStudio/.env \$HOME/AloStudio/frontend/.env.local \$HOME/infra/.env \$HOME/infra/docker-compose.yml /etc/caddy/Caddyfile"
LOCAL_DIAS=14
HC_URL=$HC_URL
HC_URL_PRUEBA=$HC_URL_PRUEBA
EOF
chmod 600 "$ENV"

set -a
# shellcheck source=/dev/null
. "$ENV"
set +a
if restic cat config > /dev/null 2>&1; then
  echo "El repositorio de copias ya existe en R2."
else
  restic init
fi

echo
echo "== 6. Primer respaldo y prueba de restauración"
bash "$REPO_DIR/respaldar.sh"
bash "$REPO_DIR/probar-restauracion.sh"
tail -n 12 "$HOME/respaldo/respaldo.log"

echo
echo "== 7. Programación (cron)"
nuevo=$(crontab -l 2>/dev/null | grep -v -e 'backup.sh' -e 'ops/respaldo/' || true)
{
  [ -n "$nuevo" ] && printf '%s\n' "$nuevo"
  echo "30 3 * * * bash $REPO_DIR/respaldar.sh"
  echo "0 5 1 * * bash $REPO_DIR/probar-restauracion.sh"
} | crontab -
crontab -l
echo
echo "Listo: respaldo diario 03:30 y prueba de restauración el día 1 a las 05:00."
