#!/usr/bin/env bash
# Puesta en marcha guiada de los respaldos en un servidor. La corre el dueño
# en su terminal (los secretos no pasan por ningún chat):
#
#   ssh -t -L 53682:127.0.0.1:53682 <usuario>@<servidor> \
#     bash AloStudio/ops/respaldo/configurar.sh
#
# El túnel del puerto 53682 deja que la autorización de Google Drive, que
# rclone espera en ese puerto del servidor, se complete desde el navegador
# de la PC.

set -Eeuo pipefail
umask 077
export PATH="$HOME/bin:$PATH"

DIR="$HOME/.config/alostudio-respaldo"
ENV="$DIR/env"
CLAVE="$DIR/clave"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DIR"
chmod 700 "$DIR"

command -v restic > /dev/null && command -v rclone > /dev/null || {
  echo "Falta restic o rclone: corré primero $REPO_DIR/instalar.sh"
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
echo "== 3. Google Drive"
if rclone listremotes | grep -qx 'gdrive:'; then
  echo "El remoto gdrive ya existe, se usa ese."
else
  echo "Se abre la autorización de Google. Copiá el enlace que aparece en el"
  echo "navegador de tu PC, entrá con tu cuenta y aceptá. rclone solo va a"
  echo "ver los archivos que él mismo cree (permiso drive.file)."
  rclone config create gdrive drive scope=drive.file config_is_local=true
fi
rclone mkdir gdrive:AloStudio-respaldos

echo
echo "== 4. Clave de cifrado de las copias"
if [ -s "$CLAVE" ]; then
  echo "Ya hay una clave en $CLAVE, se usa esa."
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
RESTIC_REPOSITORY=rclone:gdrive:AloStudio-respaldos
RESTIC_PASSWORD_FILE=$CLAVE
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

export RESTIC_REPOSITORY=rclone:gdrive:AloStudio-respaldos RESTIC_PASSWORD_FILE="$CLAVE"
if restic cat config > /dev/null 2>&1; then
  echo "El repositorio de copias ya existe en Drive."
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
