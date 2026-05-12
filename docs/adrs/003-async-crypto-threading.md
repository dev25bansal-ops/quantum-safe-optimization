# ADR-003: Async Crypto Operations via Thread Pool

**Status**: Accepted
**Date**: 2026-05-12
**Context**: Critical Bug Fixes (Phase 2)

## Decision

CPU-intensive synchronous cryptography operations (`py_encrypt`, `py_decrypt`) are offloaded from the FastAPI async event loop using `asyncio.to_thread()`.

## Rationale

### The Problem

`py_encrypt` and `py_decrypt` are synchronous, CPU-intensive calls from the Rust-backed PQC crypto module. When called directly in an `async def` endpoint handler, they block the entire event loop, causing:

- All other requests to stall during encryption/decryption
- Increased latency under load
- Potential request timeouts

### Why `asyncio.to_thread()`?

| Approach | Pros | Cons |
|---|---|---|
| `asyncio.to_thread(fn)` | Simple, built-in, auto-managed thread pool | Thread overhead (acceptable for crypto) |
| `run_in_executor()` | Custom executor control | More verbose, manual pool management |
| Rewrite crypto as async | Ideal | Requires Rust-side changes, not feasible |
| Celery offload | True async | Overkill for per-request encryption, adds infrastructure |

`asyncio.to_thread()` is the simplest correct solution. Python's default thread pool executor is sized appropriately for I/O-bound work, and crypto operations are fast enough (<100ms) that thread overhead is negligible.

## Implementation

```python
# Before (blocks event loop)
encrypted = py_encrypt(result_bytes, user_public_key)

# After (non-blocking)
encrypted = await asyncio.to_thread(py_encrypt, result_bytes, user_public_key)
```

Applied in:
- `api/routers/jobs.py` — `encrypt_result_for_user()` and `decrypt_result_for_user()`

## Consequences

### Positive
- Event loop remains responsive during crypto operations
- No changes to the Rust crypto module required
- Minimal code change

### Negative
- Slight overhead from thread scheduling (~1-2ms per operation)
- Thread pool exhaustion under extreme load (mitigated by rate limiting)
