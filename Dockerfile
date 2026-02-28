# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — FastAPI BYOK backend
#
# Multi-stage build:
#   Stage 1 (builder): install Python deps into a venv
#   Stage 2 (runtime): copy venv + source, run as non-root
#
# Usage:
#   docker build -t basivo-backend .
#   docker run -p 8000:8000 --env-file .env basivo-backend
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed by some packages (e.g. psycopg2, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to leverage layer caching
COPY requirements.txt .

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Install runtime-only native libs
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create the projects root directory.
# DOCKER MOUNT POINT: bind-mount a host directory here so OpenCode can
# read/write project files that persist beyond the container lifecycle.
#
#   docker run -v /host/path/to/projects:/app/projects basivo-backend
#
# In docker-compose.yml (see docker-compose.yml):
#   volumes:
#     - projects_data:/app/projects
RUN mkdir -p /app/projects && chown appuser:appuser /app/projects

USER appuser

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROJECTS_ROOT=/app/projects

EXPOSE 8000

# Run database migrations then start the server.
# In production you may want to run `alembic upgrade head` as a separate
# init container rather than as part of the CMD.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
