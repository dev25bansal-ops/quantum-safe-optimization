# ADR-004: Multi-Worker Job Store with Redis Cache

**Status**: Accepted
**Date**: 2026-05-12
**Context**: Critical Bug Fixes (Phase 2)

## Decision

Replace the global in-memory `_jobs_db` dictionary with a Redis-backed cache (`_jobs_cache`) backed by a persistent store (Cosmos DB or PostgreSQL). Jobs are always persisted to the durable store first, with Redis serving as a short-lived per-worker cache (TTL: 5 minutes).

## Rationale

### The Problem

The original implementation used a module-level `_jobs_db: dict[str, dict]` as the job store. In a single-process `uvicorn` deployment this works, but in gunicorn with multiple workers:

- Each worker process has its own copy of `_jobs_db`
- Job submitted to Worker A is invisible to Worker B
- Status checks from Worker B return "not found" for jobs submitted to Worker A
- Data is lost on worker restart

### Why Redis + Persistent Store?

| Approach | Pros | Cons |
|---|---|---|
| Redis cache + persistent store | Fast reads, durable writes, shared across workers | Requires Redis (already a dependency) |
| Persistent store only | Simple, single source of truth | Slower reads, more DB load |
| Shared memory (multiprocessing) | No external dependency | Doesn't work with gunicorn prefork |
| Sticky sessions | No code change | Breaks on worker restart, defeats load balancing |

Since Redis is already required for Celery task queue and rate limiting, using it as a job cache adds no new infrastructure dependency.

## Implementation

- `_jobs_cache: dict[str, dict]` — short-lived per-worker cache
- `_JOB_CACHE_TTL = 300` — 5-minute cache TTL
- `save_job()` — always writes to persistent store, updates cache
- `get_job_data()` — checks cache first, falls back to persistent store
- `save_job()` raises `RuntimeError` if no persistent store is available (no silent fallback)

## Consequences

### Positive
- Jobs are visible across all workers
- Fast reads via cache for frequently accessed jobs
- Durable storage survives worker restarts
- No silent data loss

### Negative
- Requires Redis to be running (already required)
- Slightly more complex read path (cache → store fallback)
