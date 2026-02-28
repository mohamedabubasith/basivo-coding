# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline
COPY frontend/ ./
RUN npm run build          # → /build/dist


# ── Stage 2: Production image ─────────────────────────────────────────────────
FROM python:3.12-slim

# Runtime system deps: git (workspace ops), libpq (asyncpg), curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && git config --global user.email "ai@basivo.dev" \
    && git config --global user.name  "Basivo AI"

WORKDIR /app

# Python deps (cached layer — only rebuilds when requirements.txt changes)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/     ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Built frontend (served by FastAPI via StaticFiles)
COPY --from=frontend-builder /build/dist ./frontend/dist

# All config comes from the environment — no .env file mounted or needed.
# Required env vars (set in docker-compose / k8s / cloud run):
#   DATABASE_URL, JWT_SECRET_KEY, ENCRYPTION_KEY
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROJECTS_ROOT=/app/projects \
    PORT=8000 \
    WORKERS=1

RUN mkdir -p /app/projects

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Migrate → serve
CMD ["sh", "-c", "\
    echo '[basivo] Running Alembic migrations…' && \
    PYTHONPATH=/app alembic upgrade head && \
    echo '[basivo] Starting server on 0.0.0.0:'${PORT} && \
    exec uvicorn app.main:app \
        --host 0.0.0.0 --port ${PORT} --workers ${WORKERS} --log-level info \
"]
