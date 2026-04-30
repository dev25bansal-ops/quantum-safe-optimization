# Quantum-Safe Optimization Platform - Production Dockerfile
# Multi-stage build for optimized image size

# ===========================
# Stage 1: Base image with dependencies
# ===========================
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
COPY README.md .

RUN pip install --upgrade pip && \
    pip install . && \
    pip install gunicorn uvicorn[standard]

# ===========================
# Stage 2: Development image
# ===========================
FROM base as development

ENV APP_ENV=development

# Install development dependencies
COPY pyproject.toml .
RUN pip install -e ".[dev]" && \
    pip install pytest-cov

# Copy source code
COPY . .

# Expose port
EXPOSE 8000

# Run with auto-reload
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ===========================
# Stage 3: Production image
# ===========================
FROM base as production

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

ENV APP_ENV=production

# Copy application code
COPY src/qsop src/qsop
COPY api/ api/
COPY quantum_safe_crypto*.py .
COPY alembic.ini .
COPY alembic/ alembic/

# Set ownership
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run with gunicorn workers
CMD ["gunicorn", "api.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--capture-output"]

# ===========================
# Stage 4: Minimal image for serverless
# ===========================
FROM python:3.11-slim as minimal

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install only required packages
WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir gunicorn

# Copy only necessary files
COPY src/qsop src/qsop
COPY api/ api/
COPY quantum_safe_crypto*.py .

# Expose port
EXPOSE 8000

# Run minimal version
CMD ["gunicorn", "api.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker"]