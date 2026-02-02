# Multi-stage Dockerfile for Quantum-Safe Optimization Platform
# Builds Rust crypto module and Python application

# Stage 1: Build Rust crypto module
FROM rust:1.75-bookworm AS rust-builder

WORKDIR /build

# Install Python headers for PyO3
RUN apt-get update && apt-get install -y \
    python3-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Copy Rust project
COPY crypto/ ./crypto/

WORKDIR /build/crypto

# Build the Rust library
RUN cargo build --release

# Build Python wheel using maturin
RUN pip3 install maturin && \
    maturin build --release --out /build/wheels


# Stage 2: Python application
FROM python:3.11-slim-bookworm AS python-base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgomp1 \
    libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Install Python dependencies
COPY api/requirements.txt ./api/
COPY optimization/pyproject.toml ./optimization/

RUN pip install --no-cache-dir -r api/requirements.txt

# Copy the built Rust wheel from builder stage
COPY --from=rust-builder /build/wheels/*.whl /tmp/wheels/
RUN pip install /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Copy application code
COPY api/ ./api/
COPY optimization/ ./optimization/

# Install optimization package
RUN pip install -e ./optimization

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]


# Stage 3: Development image with additional tools
FROM python-base AS development

USER root

# Install development dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    black \
    ruff \
    mypy \
    ipython

USER appuser

# Override CMD for development
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
