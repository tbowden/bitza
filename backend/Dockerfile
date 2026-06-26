# ---------------------------------------------------------------------------
# Stage 1: dependency builder using uv
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Copy uv binary from the official image — avoids a curl/install step.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifest first (layer-cache friendly).
COPY pyproject.toml .python-version ./

# Install production dependencies only (no dev extras) into /app/.venv.
# --frozen: fail if uv.lock is out of date (ensures reproducible builds).
# --no-install-project: install deps without the project itself at this stage.
RUN uv sync --frozen --no-install-project --no-group dev


# ---------------------------------------------------------------------------
# Stage 2: runtime image
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Create a non-root user.
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Copy the virtual environment from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Copy application source and migration files.
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY app/ ./app/

# Ensure the venv is on PATH.
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Persistent data directory (mounted as a Docker volume).
RUN mkdir -p /app/data && chown appuser:appgroup /app/data

USER appuser

EXPOSE 8000

# Run migrations then start the server.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log"]
