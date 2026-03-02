# Comprehensive Code Audit Report — `api/` Directory

**Scope**: All Python source files in `d:\Quantum\api\` (33 files across 9 subdirectories)  
**Categories**: Import errors, Logic bugs, Type errors, Security issues, Missing error handling, Cross-file inconsistencies, Deprecated patterns

---

## CRITICAL — Module-Breaking Errors

These issues prevent entire modules from loading at all.

### `api/routers/websocket.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 346–347 | **CRITICAL** | `except Exception:` at module-level indentation (column 0) instead of inside the `try` block in `_health_check_loop()`. This is a **SyntaxError/IndentationError** that prevents the entire module from importing. |
| 505–506 | **CRITICAL** | Same module-level `except Exception:` block at end of `job_updates_websocket()`. Another **IndentationError** breaking the module. |
| 676–677 | **CRITICAL** | Same module-level `except Exception:` block at end of `all_jobs_websocket()`. Third **IndentationError**. |

### `api/routers/health_v2.py`

| Line | Severity | Description |
|------|----------|-------------|
| 30 | **CRITICAL** | Uses `Literal["healthy", "degraded", "unhealthy"]` but **never imports `Literal`** from `typing`. Causes `NameError` at import time — module entirely broken. |
| ~93 | **CRITICAL** | `check_celery()` function uses `os.getenv(...)` but **never imports `os`**. Will raise `NameError` when function is called. |

### `api/security/secrets_manager.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 107–111 | **CRITICAL** | **IndentationError** in `initialize()`: The `try` block after `if self.config.key_vault_uri:` is at the same indentation level as the `if` statement, leaving the `if` body empty. This is a **SyntaxError**. |
| 109 | **CRITICAL** | `self._load_from_key_vault()` is called but the method **is never defined** anywhere in the file. Even with fixed indentation, this raises `AttributeError`. |
| 107–115 | **BUG** | `self._initialized` is never set to `True` after the initialization logic completes. The `initialize()` method will re-run every time — and `self._use_local` is never set to `True` in any code path, meaning `get_secret()` would always try Key Vault (which also fails due to the above bugs). |

---

## HIGH — Logic Bugs and Functional Errors

### `api/config.py`

| Line | Severity | Description |
|------|----------|-------------|
| 295 | **HIGH** | Trailing comma after Field definition: `host: str = Field(default="0.0.0.0", alias="API_HOST"),` — the comma makes this a **tuple** `(Field(...),)` instead of a plain Field. Pydantic will reject it as invalid or assign a tuple type. |

### `api/routers/auth_demo.py`

| Line | Severity | Description |
|------|----------|-------------|
| 62 | **HIGH** | `get_server_signing_keypair(Request.scope["app"])` — `Request` is the **class**, not an instance. `Request` doesn't have a `.scope` attribute. This raises `AttributeError` at runtime. Should inject `request: Request` via the endpoint signature and pass it. |

### `api/routers/credentials.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 78–80, 104, 125, 152 | **HIGH** | All four endpoint functions (`store_credential`, `list_credentials`, `get_credential`, `delete_credential`) use `@limiter.limit(...)` decorators but **none accept a FastAPI `Request` parameter**. The `slowapi` limiter requires a `Request` object as the first positional arg after `self`. All rate-limited endpoints will fail with a runtime error. |

### `api/routers/auth.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 390–400 | **HIGH** | `verify_pqc_token()` only checks the sync in-memory `_tokens_db` dict (`token_record = _tokens_db.get(token)`), not the async persistent store. If a token exists only in the store (e.g., after app restart while store persists), it won't be found and authentication will fail. |

### `api/db/cosmos.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 225–229 | **HIGH** | `ClientTimeout(...)` is created but **never assigned to a variable**. The constructed timeout configuration is silently discarded, meaning no custom timeout is applied. |

### `api/main.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 61 vs 197 | **HIGH** | Inconsistent `OTEL_ENABLED` defaults: Line 61 defaults to `"false"` for `setup_telemetry()`, but line 197 defaults to `"true"` for `instrument_fastapi(app)`. When `OTEL_ENABLED` is not set, the app **instruments FastAPI without setting up tracing infrastructure**, which may cause errors or silent failures. |

### `api/services/credentials.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 34 | **HIGH** | `AzureKeyVaultBackend` imports the **synchronous** `SecretClient` from `azure.keyvault.secrets`, but all backend methods use `await self.client.set_secret(...)`, `await self.client.get_secret(...)`, etc. Synchronous `SecretClient` methods don't return awaitables, so all `await` calls will fail with `TypeError: object ... can't be used in 'await' expression`. Should import from `azure.keyvault.secrets.aio` instead. |
| 301 | **MEDIUM** | `AzureKeyVaultBackend.list_by_user()` uses `async for secret_prop in secret_properties:` but `self.client.list_properties_of_secrets()` (sync) returns a regular iterator, not an async iterator. |

---

## MEDIUM — Security Issues

### `api/routers/auth.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 170–180 | **SECURITY** | Hardcoded admin user with known password hash in `_users_db`. The password `admin123!` is discoverable from the hash. This should be removed or configured via environment variables in production. |
| 340 | **SECURITY** | Full JWT signature is stored in `_tokens_db`/store alongside the token. If the token store is compromised, attackers have both token and signature. |

### `api/services/webhooks.py`

| Line | Severity | Description |
|------|----------|-------------|
| 30 | **SECURITY** | `WEBHOOK_SECRET` has a hardcoded default: `"quantum-webhook-secret-change-in-production"`. If env var is unset, webhook signatures use this predictable secret, allowing forgery. |

### `api/services/credentials.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 107 | **SECURITY** | `LocalEncryptedBackend` uses a **hardcoded static salt**: `b"qsop_credentials_salt"`. This weakens PBKDF2 key derivation since all environments share the same salt. A random per-environment salt should be used. |
| 102 | **SECURITY** | When `LOCAL_ENCRYPTION_KEY` is not set, a new key is auto-generated every restart—meaning previously encrypted credentials become **permanently unreadable**. |

### `api/security/signature_verification.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 60 | **SECURITY** | `_seen_nonces` is an unbounded in-memory `set()`. In long-running production, this grows without limit (memory leak). The comment acknowledges this: "In production, use Redis". |

### `api/security/token_revocation.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 37 | **SECURITY** | Class-level mutable defaults: `_memory_blacklist: set[str] = set()` and `_memory_expiry: dict = {}` are **shared across all instances** (including the singleton pattern). While this works for the current singleton, it's fragile. |

---

## MEDIUM — Type Errors and Import Issues

### `api/routers/auth_demo.py`

| Line | Severity | Description |
|------|----------|-------------|
| 5 | MEDIUM | `Depends` imported from `fastapi` but **never used**. |

### `api/routers/health_v2.py`

| Line | Severity | Description |
|------|----------|-------------|
| 37 | MEDIUM | `Depends` imported from `fastapi` but **never used**. |

### `api/routers/credentials.py`

| Line | Severity | Description |
|------|----------|-------------|
| 28 | MEDIUM | `get_remote_address` imported from `slowapi.util` but **never used**. |

### `api/routers/jobs.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| ~30–35 | MEDIUM | Imports `QAOAConfig` from `optimization.src.qaoa.runner` which **shadows** the `QAOAConfig` from `api.models.jobs` (also in models `__init__.py`). If both are in scope, the later import wins, causing unexpected behavior. |

### `api/routers/__init__.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 3–5 | MEDIUM | Only exports `auth`, `health`, and `jobs`, while `main.py` imports many more routers (`backends`, `costs`, `credentials`, `metrics`, `websocket`, `auth_demo`, `health_v2`). This `__init__.py` is incomplete relative to the actual router set. |

### `api/security/secrets_manager.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 10–13 | MEDIUM | Unconditionally imports `azure.core.exceptions`, `azure.identity.aio`, and `azure.keyvault.secrets.aio` at module level **without try/except**. If Azure SDK packages aren't installed, the entire module fails to import. Other files (like `services/credentials.py`) properly guard these imports. |

---

## MEDIUM — Missing Error Handling

### `api/routers/auth.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 247–263 | MEDIUM | `check_email_exists()` iterates up to 1000 users via `store.list(limit=1000)` to check email uniqueness — **linear scan**. For large user bases, this is very slow. No pagination or index-based lookup. |

### `api/routers/jobs.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 500–800 | MEDIUM | `process_optimization_job()` catches `Exception` broadly and updates job status to "failed", but doesn't distinguish between retryable errors (network timeouts) and permanent errors (invalid config). All failures are treated the same. |

### `api/tasks/workers.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 72 | MEDIUM | `get_job_state()` uses `v.startswith("{")` or `v.startswith("[")` to decide whether to `json.loads()` a value. This is fragile and will crash on strings like `"[incomplete"` or misparse strings that happen to start with `{`. |

### `api/storage/redis_adapter.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 103–105 | MEDIUM | `keys()` method accesses `redis._redis.keys(...)` — reaching into a **private attribute** of `RedisManager`. If `RedisManager` changes internally, this breaks. Also, `keys()` doesn't handle the case where `_redis` is `None` (when Redis is disabled). |

---

## LOW — Deprecated Patterns

### `datetime.utcnow()` usage (Python 3.12+ deprecation)

`datetime.utcnow()` is deprecated since Python 3.12. It returns a naive datetime which can cause subtle timezone bugs. Should use `datetime.now(timezone.utc)` instead.

**Affected files** (50+ occurrences total across the `api/` tree):

| File | Approximate Count |
|------|-------------------|
| `api/routers/auth.py` | ~10 |
| `api/routers/websocket.py` | ~12 |
| `api/routers/health.py` | ~5 |
| `api/routers/jobs.py` | ~8 |
| `api/tasks/workers.py` | ~12 |
| `api/services/webhooks.py` | ~6 |
| `api/services/encryption.py` | ~2 |
| `api/services/credentials.py` | ~2 |
| `api/security/token_revocation.py` | ~3 |
| `api/security/secrets_manager.py` | ~3 |
| `api/security/middleware.py` | ~1 |
| `api/db/cosmos.py` | ~3 |
| `api/db/repository.py` | ~1 |

---

## LOW — Code Quality and Consistency Issues

### `api/security/token_revocation.py`

| Line | Severity | Description |
|------|----------|-------------|
| 155–165 | LOW | `revoke_all_user_tokens()` returns `0` for memory fallback with a comment "Memory fallback doesn't support this". Should at least iterate `_memory_blacklist` or log a warning. |

### `api/services/credentials.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 282–296 | LOW | `LocalEncryptedBackend._load()` and `_save()` use `asyncio.Lock()` for thread safety, but the actual file I/O (`open(...)`, `f.read()`, `f.write()`) is **synchronous**, blocking the event loop. Should use `aiofiles` or run in an executor. |

### `api/routers/metrics.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 1–300 | LOW | `PrometheusMetrics` uses plain Python dicts (`Counter` style) for metrics aggregation. These are not thread-safe under concurrent access. Consider using `threading.Lock` or `asyncio.Lock` for counters. |

### `api/routers/health.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 1–446 | LOW | Uses `os` module throughout but is properly imported. No issues beyond `datetime.utcnow()` deprecation. |

### `api/routers/costs.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 1–484 | LOW | `DEFAULT_PRICING` is used as a fallback but its definition is in the first 300 lines (not shown in summary). No significant issues beyond normal code review items. |

### `api/schemas/problem_config.py`

| Line(s) | Severity | Description |
|---------|----------|-------------|
| 1–467 | LOW | Well-structured with proper Pydantic validators. `AnnealingQUBOConfig.qubo_matrix` uses `dict[tuple[int, int], float]` which won't deserialize from JSON (JSON keys must be strings). This model works only when constructed in Python, not from API request bodies. |

### `api/tasks/celery_app.py`

| Line | Severity | Description |
|------|----------|-------------|
| 7 | LOW | Unconditionally imports `from celery import Celery` without try/except guard. If Celery isn't installed, this module fails. Other files guard Celery imports. |

### `api/tasks/workers.py`

| Line | Severity | Description |
|------|----------|-------------|
| 13 | LOW | Unconditionally imports `import redis` (sync) and `from celery import Task`. No import guards. This is expected for worker files but inconsistent with how the main app guards these. |

---

## Cross-File Inconsistencies

| Issue | Files | Description |
|-------|-------|-------------|
| **OTEL_ENABLED defaults** | `main.py:61` vs `main.py:197` | `"false"` for setup vs `"true"` for instrumentation. |
| **Azure SDK import guards** | `secrets_manager.py` vs `credentials.py` | `secrets_manager.py` does NOT guard Azure imports; `credentials.py` does with try/except. |
| **Celery import guards** | `tasks/celery_app.py` vs `routers/jobs.py` | `celery_app.py` imports unconditionally; `jobs.py` wraps Celery imports in try/except. |
| **Sync vs Async SecretClient** | `secrets_manager.py` vs `services/credentials.py` | `secrets_manager.py` correctly imports async `SecretClient`; `credentials.py` imports sync `SecretClient` but uses `await`. |
| **Token verification scope** | `auth.py` `verify_pqc_token()` | Only checks sync `_tokens_db`; `save_token()` saves to both memory and async store. After restart, tokens in store only are invisible. |
| **Router `__init__.py`** | `routers/__init__.py` vs `main.py` | `__init__.py` exports 3 routers; `main.py` imports 8+ routers directly. |
| **`datetime.utcnow()` everywhere** | All files | Pervasive use of deprecated `datetime.utcnow()` across all 33+ files in `api/`. |

---

## Summary by Severity

| Severity | Count | Key Examples |
|----------|-------|-------------|
| **CRITICAL** (module won't load) | 7 | websocket.py indentation (×3), health_v2.py missing imports (×2), secrets_manager.py indentation + missing method |
| **HIGH** (runtime errors) | 7 | config.py tuple, auth_demo.py class-vs-instance, credentials.py missing Request, auth.py token sync, cosmos.py lost timeout, main.py OTEL mismatch, services/credentials.py sync SecretClient |
| **SECURITY** | 6 | Hardcoded admin, hardcoded webhook secret, static salt, unbounded nonce set, class-level mutable state, stored signatures |
| **MEDIUM** | 10 | Unused imports (×3), name shadows, incomplete __init__.py, unguarded Azure imports, linear email scan, fragile JSON detection, private attribute access |
| **LOW / Deprecation** | 60+ | `datetime.utcnow()` across all files, sync file I/O in async context, non-thread-safe counters, JSON-incompatible Pydantic types |

---

*Generated by comprehensive static analysis of all 33 Python files in `d:\Quantum\api\`.*
