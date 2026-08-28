# syntax=docker/dockerfile:1.6
# ---------------------------------------------------------------------------
# Learning 360° (l360) — room-booking + billing tool for Learning 360°
# Foundation (Malta) educators (FastAPI + React SPA).
# A fully separate standalone app, isolated from kitchentable and the
# retail/POS system — its own Fly app (l360/fly.toml), own Neon Postgres
# project/schema (`l360`), own GitHub Actions workflows. It shares nothing at
# runtime with the other apps in this repo.
#
# Two stages: build the React app with Node, then serve it + the API with
# Python/uvicorn.
# ---------------------------------------------------------------------------

# --- stage 1: build the React SPA ------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY l360/web/package.json l360/web/package-lock.json ./
RUN npm ci
COPY l360/web/ ./
COPY l360/design/ /design/
RUN npm run build          # emits /web/dist

# --- stage 2: python API server --------------------------------------------
FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY l360/requirements.txt ./
RUN pip install -r requirements.txt

# Ship only this app's package; the built SPA comes from stage 1.
COPY l360 ./l360
COPY --from=web /web/dist ./l360/web/dist

ENV PORT=8000 \
    UVICORN_WORKERS=2

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# init_db() is a NO-OP on Postgres (the `l360` schema is owned by gated
# Alembic, never boot). Then start uvicorn.
CMD ["/bin/sh", "-c", "python -c 'from l360.db import init_db; init_db()' && uvicorn l360.api:app --host 0.0.0.0 --port ${PORT} --workers ${UVICORN_WORKERS}"]
