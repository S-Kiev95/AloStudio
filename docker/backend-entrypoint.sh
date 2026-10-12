#!/bin/sh
# Backend container entrypoint: apply pending migrations, then serve the API.
# The ARQ worker runs the same image with a direct `arq` command instead —
# it must not race migrations against this process.
set -e

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
