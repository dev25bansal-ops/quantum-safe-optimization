# ADR-001: Dual Entry Points

**Status**: Accepted
**Date**: 2026-05-12
**Context**: Architecture Consolidation (Phase 3)

## Decision

The project maintains two FastAPI application entry points:

1. **`api/main.py`** — Primary entry point for development and direct `uvicorn` usage
2. **`api/app_factory.py`** — Factory-based entry point for production (gunicorn workers, proper key store initialization)
3. **`src/qsop/main.py`** — Legacy entry point (deprecated, kept for backward compatibility)

## Rationale

### Why not a single entry point?

During Phase 3 we evaluated consolidating to a single entry point but determined that:

1. **`api/main.py`** is tightly coupled to `uvicorn --reload` development workflows and imports modules directly
2. **`api/app_factory.py`** uses the `app_factory` pattern required by gunicorn for multi-worker deployments with proper shared state (Redis-backed job store, persistent key rotation)
3. Merging them would introduce conditional logic (`if dev: ... else: ...`) that reduces clarity

### Migration path

- `api/main.py` now imports from `api/app_factory.py` where possible, acting as a thin wrapper
- `src/qsop/main.py` is marked deprecated with a startup warning
- All new features are added to `api/app_factory.py` only

## Consequences

### Positive
- Clear separation between dev and prod entry patterns
- `app_factory.py` is the single source of truth for application assembly
- No conditional complexity in either entry point

### Negative
- Developers must know which entry point to use
- `src/qsop/main.py` maintenance burden until fully removed

## Alternatives Considered

| Alternative | Rejected Because |
|---|---|
| Single entry point with env-based branching | Introduces conditional complexity, harder to reason about |
| Remove `api/main.py` entirely | Breaks simple `uvicorn api.main:app` dev workflow |
| Merge everything into `src/qsop/main.py` | That file uses different patterns and would require full rewrite |
