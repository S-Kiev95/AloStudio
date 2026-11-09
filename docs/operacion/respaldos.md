# Respaldos

Política acordada el 2026-11-09 (F1 de `PLAN.fases-futuras.md`). Scripts en
`ops/respaldo/`.

## Qué se respalda y dónde

| Qué | Cómo |
|---|---|
| Base Postgres | `pg_dump -Fc`, verificado con `pg_restore --list` |
| Archivos de MinIO (adjuntos, medios) | tar del volumen, leído por un contenedor |
| Configuración | `.env` del backend, frontend e infra, `docker-compose.yml`, `Caddyfile`, crontab y unidades systemd |

- **Afuera:** restic, cifrado con la clave del servidor, en el bucket
  `alostudio-respaldos` de Cloudflare R2 (compatible con S3; 10 GB gratis y
  sin cobro por descargar, así que restaurar no cuesta). Cada servidor en
  su carpeta (`/ctc`, `/develop`). Se eligió R2 y no Google Drive para no
  depender de una suscripción personal.
- **Adentro:** los volcados de la base de los últimos 14 días en
  `~/backups/`, para restaurar rápido.
- **Retención afuera:** 7 diarios, 4 semanales, 12 mensuales. Un respaldo
  nuevo no borra el anterior: restic guarda cada copia como una "foto" y
  solo sube lo que cambió; `forget --prune` descarta las fotos que quedan
  fuera de esa retención.
- **Objetivos:** perder como máximo 24 h de datos; volver a estar arriba en
  menos de 4 h.

## Cuándo corre

| Cron | Script |
|---|---|
| todos los días 03:30 | `respaldar.sh`; los domingos además `restic check` sobre el 10 % de los datos |
| día 1 de cada mes 05:00 | `probar-restauracion.sh`: restaura la última copia en un Postgres temporal sin red y compara conteos |

Log: `~/respaldo/respaldo.log`.

**Avisos:** Healthchecks.io, dos chequeos por servidor (respaldo diario y
prueba mensual). Si un respaldo falla, o no avisa a tiempo porque el
servidor o el cron se cayeron, llega un correo.

## Puesta en marcha en un servidor

1. `git pull` del repo y `bash ~/AloStudio/ops/respaldo/instalar.sh`
   (instala restic en `~/bin`, con checksum verificado; sin sudo).
2. En Cloudflare (una sola vez, sirve para todos los servidores):
   - R2 → crear el bucket `alostudio-respaldos`.
   - R2 → Manage API tokens → crear un token con permiso **Object Read &
     Write** aplicado **solo a ese bucket**. Anotar el Access Key ID y el
     Secret Access Key (el secreto se muestra una vez).
   - El Account ID está en la página de R2.
3. En Healthchecks.io crear dos chequeos con zona horaria
   `America/Montevideo`:
   - "AloStudio <servidor> respaldo": cron `30 3 * * *`, gracia 1 h.
   - "AloStudio <servidor> restauración": cron `0 5 1 * *`, gracia 2 h.
4. Desde la PC: `ssh -t <usuario>@<servidor> bash AloStudio/ops/respaldo/configurar.sh`
   Pide el nombre del servidor, el volumen de MinIO, los datos de R2, genera
   la clave (mostrarla una vez y **guardarla en el gestor de contraseñas**),
   pide las dos URLs de Healthchecks, hace el primer respaldo, la primera
   prueba de restauración y programa el cron.

Archivos que quedan en el servidor (permisos 600):
`~/.config/alostudio-respaldo/env` (claves de R2 y URLs de aviso) y
`~/.config/alostudio-respaldo/clave`.

## Restaurar

Siempre primero en una base aparte, nunca encima de la de producción sin
haberla mirado.

**Base, desde el disco local (lo más rápido):**

```bash
ls ~/backups/
docker exec -i alostudio-postgres pg_restore -U alostudio -d alostudio --clean --if-exists --no-owner < ~/backups/alostudio-AAAA-MM-DD.dump
```

**Desde R2** (servidor nuevo o disco perdido):

```bash
export PATH="$HOME/bin:$PATH"
set -a; . ~/.config/alostudio-respaldo/env; set +a   # en un servidor nuevo: crear env y clave como en env.ejemplo
restic snapshots --host ctc
restic restore latest --host ctc --target ~/restaurado
```

Dentro de `~/restaurado/.../etapa/` quedan:

- `base.dump`: `pg_restore` como arriba.
- `minio.tar`: con MinIO parado,
  `docker run --rm -i -v alostudio_minio_data:/data alpine:3 tar -C /data -xf - < minio.tar`.
- `config/`: los `.env`, el `docker-compose.yml`, el `Caddyfile`
  (los `/` del camino original están como `__`), el crontab y las unidades
  systemd.
- `conteos.txt`: filas y archivos al momento del respaldo, para comparar.

**Servidor nuevo desde cero:** instalar Docker y Caddy, clonar el repo,
copiar `config/` a su lugar, `docker compose up -d` en `~/infra`, restaurar
la base y MinIO, compilar el frontend, levantar los servicios systemd y
apuntar el DNS. Después, `instalar.sh` y `configurar.sh` con la misma clave.

## Si llega un aviso

1. `tail -n 40 ~/respaldo/respaldo.log` en el servidor.
2. Error de acceso a R2 (token borrado o vencido): crear otro token como en
   el paso 2 y reemplazar `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` en
   `~/.config/alostudio-respaldo/env`.
3. Correr a mano `bash ~/AloStudio/ops/respaldo/respaldar.sh` y confirmar
   que el chequeo vuelve a verde.
