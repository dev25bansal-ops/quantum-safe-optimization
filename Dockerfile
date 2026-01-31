# syntax=docker/dockerfile:1.4

# =============================================================================
# Quantum-Safe Secure Optimization Platform - Production Dockerfile
# =============================================================================

# -----------------------------------------------------------------------------
# Build stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip setuptools wheel \
    && pip install .

# -----------------------------------------------------------------------------
# Runtime stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

LABEL maintainer="QSOP Team <team@qsop.dev>" \
    version="0.1.0" \
    description="Quantum-Safe Secure Optimization Platform"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:$PATH" \
    QSOP_ENV=prod \
    QSOP_API_HOST=0.0.0.0 \
    QSOP_API_PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 qsop \
    && useradd --uid 1000 --gid qsop --shell /bin/bash --create-home qsop

COPY --from=builder /opt/venv /opt/venv
COPY --chown=qsop:qsop src ./src

RUN mkdir -p /app/data && chown -R qsop:qsop /app/data

USER qsop

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["qsop.main:app", "--host", "0.0.0.0", "--port", "8000"]
