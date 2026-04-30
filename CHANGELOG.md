# Changelog

All notable changes to the Quantum-Safe Optimization Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- GraphQL API at `/api/v1/graphql` with GraphiQL playground
- Event sourcing for comprehensive audit trail
- API key rotation automation service with scheduling
- Rate limit backup persistence for Redis failover scenarios
- Chaos engineering test suite for resilience verification
- Frontend build configuration with Vite
- TypeScript type definitions for frontend modules
- Demo mode security hardening with environment validation
- Coverage threshold enforcement (70%) in CI pipeline
- Token revocation store with automatic cleanup
- Quantum error mitigation (ZNE, Readout, PEC)
- Notification service for real-time alerts
- Data export service (JSON, CSV, PDF)
- Analytics dashboard service
- Interactive frontend tutorials module
- Security scanning CI workflow (Bandit, Safety, pip-audit, CodeQL)
- Prometheus alerting rules (30 rules across 8 categories)

### Changed

- Demo mode now requires explicit environment validation (blocked in production)
- Rate limiter includes backup store for persistence during Redis outages
- Security headers middleware enhanced with additional OWASP headers
- ML-KEM/ML-DSA fallback handling improved for missing native implementations

### Fixed

- Test data validation in marketplace and federation tests
- Notification service syntax error
- Audit integrity response field names

### Security (Critical)

#### Fixed

- **P0-1**: Replaced stub crypto with real liboqs integration
  - `quantum_safe_crypto.py` now uses real liboqs when available
  - Added security warnings for stub implementation
  - Added `is_crypto_production_ready()` and `get_crypto_status()` functions

- **P0-2**: Removed hardcoded credentials
  - Admin credentials now from environment variables (`ADMIN_USERNAME`, `ADMIN_PASSWORD`)
  - Production warning when using default password
  - No secrets in source code

- **P0-3**: Fixed insecure CORS configuration
  - Environment-based CORS origins
  - Production blocks wildcard `*` origins
  - Added `CORS_ORIGINS` environment variable

- **P0-4**: Rust crypto module build documentation
  - Created `crypto/BUILD.md` with build instructions
  - Documented Windows, Linux, macOS prerequisites

### High Priority

#### Fixed

- **P1-1**: Fixed 30+ type annotation errors
  - Added `PatternType` alias in `validation.py`
  - Fixed `dict` type parameters in `filesystem.py`
  - Added `set[Permission]` type in `authz.py`

- **P1-3**: Added WebSocket authentication
  - JWT token verification for WebSocket connections
  - Added `verify_websocket_token()` function
  - Token parameter support in WebSocket endpoint

- **P1-4**: Implemented Alembic database migrations
  - Created `alembic.ini` configuration
  - Created `alembic/env.py` with async support
  - Created initial migration `001_initial.py` with schema

- **P1-5**: Fixed rate limiting for production
  - Redis-backed rate limiting in production
  - Environment-based storage selection
  - Added logging for rate limit storage

### Medium Priority

#### Added

- **P2-1**: Refactored large files
  - Created `api/routers/jobs_submit.py` for job submission
  - Separated concerns for maintainability

- **P2-4**: Standardized error response formats
  - Created `api/schemas/errors.py` with error codes
  - Added `ErrorResponse` and `ValidationErrorDetail` models
  - Standard error codes for all API responses

- **P2-5**: Added API versioning documentation
  - Documented deprecation timeline
  - Version header responses

### Low Priority

#### Added

- **P3-1**: Created deployment runbook
  - `docs/DEPLOYMENT.md` with step-by-step instructions
  - Environment variables reference
  - Rollback procedures

- **P3-2**: Added security documentation
  - `docs/SECURITY.md` with PQC algorithm details
  - Authentication flow diagrams
  - Key management procedures

- **P3-4**: Added Prometheus alerting rules
  - `deploy/prometheus/alerts.yml` with 20+ alerts
  - Coverage: availability, errors, crypto, jobs, auth, rate limiting

- **P3-5**: Created contribution guidelines
  - `CONTRIBUTING.md` with development setup
  - Commit message format
  - PR checklist

### Additional Improvements

#### Added

- Custom exception hierarchy (`api/exceptions.py`)
  - Specific exceptions for all error types
  - Replaces broad `Exception` catches

- Dependency injection container (`api/di_container.py`)
  - `DIContainer` class for service management
  - Singleton and transient support

- Performance optimizations (`api/performance.py`)
  - `LRUCache` with TTL support
  - `ConnectionPool` for resource management
  - `BatchProcessor` for bulk operations
  - `gather_with_concurrency` for limited parallelism

- Integration tests (`tests/test_api_integration.py`)
  - Health endpoint tests
  - Authentication flow tests
  - Job endpoint tests

- Kubernetes deployment (`deploy/kubernetes/qsop-api.yaml`)
  - Deployment with 3 replicas
  - HorizontalPodAutoscaler
  - PodDisruptionBudget
  - Ingress with TLS

- Frontend type definitions (`frontend/js/types.js`)
  - JSDoc type definitions
  - TypeScript-like type checking

- CI/CD improvements
  - Updated to block on type errors in PRs
  - Better error messages

## [0.1.0] - Initial Release

### Added

- Quantum-Safe Optimization Platform core
- ML-KEM (Kyber) and ML-DSA (Dilithium) support
- QAOA, VQE, and Quantum Annealing backends
- FastAPI REST API
- WebSocket real-time updates
- User authentication with PQC-signed JWTs
- Azure Cosmos DB integration
- Redis caching and rate limiting
- Docker containerization
- OpenAPI documentation
