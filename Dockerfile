# syntax=docker/dockerfile:1
# AloStudio backend (FastAPI + ARQ worker share this image).

# ---- dependency builder --------------------------------------------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Lockfile-only layer first so dependency install is cached independently
# of application code changes.
COPY pyproject.toml uv.lock ./
# All runtime deps ship binary wheels; the build-essential fallback covers
# a future dep that only ships an sdist (kept out of the final image).
RUN uv sync --frozen --no-dev --no-install-project \
    || (apt-get update \
        && apt-get install -y --no-install-recommends build-essential \
        && uv sync --frozen --no-dev --no-install-project)

# ---- runtime --------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY docker ./docker
RUN chmod +x docker/backend-entrypoint.sh

EXPOSE 8000

# Default command runs the API; the worker service overrides it with arq.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
