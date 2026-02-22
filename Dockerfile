# ---------------------------------------------------------------------------
# Multi-stage Dockerfile for the FastAPI portfolio service.
#
# Stage 1 (builder) — installs Python dependencies into an isolated prefix.
# Stage 2 (runtime) — lean final image; copies only what is needed to run.
#
# Build:  docker build -t portfolio-api .
# Run:    docker run --env-file .env -p 8000:8000 portfolio-api
# ---------------------------------------------------------------------------

# ---- Stage 1: builder -------------------------------------------------------
FROM python:3.12-slim AS builder

# Prevent .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Copy dependency manifest first to exploit Docker layer caching
COPY requirements.txt .

# Install dependencies into a custom prefix so Stage 2 can copy them cleanly
RUN pip install --prefix=/install -r requirements.txt


# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create a non-root system user and group
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --no-create-home appuser

WORKDIR /app

# Pull installed packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application source code and scripts
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Switch to non-root user before the final CMD
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
