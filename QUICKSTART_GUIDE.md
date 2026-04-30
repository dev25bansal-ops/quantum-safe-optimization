# Quantum-Safe Optimization Platform - Quick Start Guide

## 🚀 Getting Started After Improvements

This guide shows you how to use the newly implemented improvements.

---

## 1. Security Improvements

### 1.1 Key Rotation Configuration

The platform now automatically rotates PQC keys. Configure via environment variables:

```bash
# .env file
PQC_KEY_MAX_AGE_DAYS=90        # Keys expire after 90 days
PQC_KEY_ROTATE_BEFORE_DAYS=7   # Start rotating 7 days before expiry
```

**Check key rotation status:**
```bash
curl http://localhost:8000/api/v1/health/detailed | jq .components.pqc_crypto
```

### 1.2 Error Handling (Production Safe)

Errors are now safely handled:
- **Development:** Full error messages for debugging
- **Production:** Generic messages (no information leak)

Controlled by `APP_ENV` (not `DEBUG`):
```bash
APP_ENV=development    # Shows full errors (for local dev only)
APP_ENV=production     # Shows generic errors (default)
```

---

## 2. Performance Optimizations

### 2.1 Email Lookup (Now O(1))

No configuration needed - automatic optimization!

**Before:**
```
Registration with 1,000 users: 50ms+
Email check: Scans ALL users
```

**After:**
```
Registration with 1,000 users: <1ms
Email check: O(1) hash map lookup
```

### 2.2 Result Caching

Enable caching for repeated quantum optimization problems:

```bash
# .env file
REDIS_URL=redis://localhost:6379/0
RESULT_CACHE_ENABLED=true
RESULT_CACHE_TTL=300  # 5 minutes
```

**Usage in code:**
```python
from api.cache.result_cache import init_result_cache, get_result_cache

# Initialize at startup
await init_result_cache(
    redis_url="redis://localhost:6379/0",
    ttl=300,
    enabled=True
)

# Use in job processing
cache = get_result_cache()

# Check cache before computing
cached_result = await cache.get(problem_config, parameters)
if cached_result:
    return cached_result  # <5ms!

# Compute and cache result
result = await solve_quantum_problem(problem_config, parameters)
await cache.set(problem_config, parameters, result)
```

**Check cache stats:**
```bash
curl http://localhost:8000/api/v1/cache/stats
```

Response:
```json
{
  "hits": 150,
  "misses": 50,
  "hit_rate": 0.75,
  "total_requests": 200,
  "cached_results": 45,
  "ttl_seconds": 300
}
```

---

## 3. Strategy Pattern for Job Processing

### 3.1 Using the Processor Registry

**Old way (still works but deprecated):**
```python
if problem_type == "QAOA":
    # 100 lines of QAOA code
elif problem_type == "VQE":
    # 80 lines of VQE code
```

**New way (recommended):**
```python
from api.routers.jobs.processors.registry import (
    solve_problem,
    get_supported_problem_types,
    registry
)

# Get supported problem types
types = get_supported_problem_types()
# Returns: ["QAOA", "VQE", "ANNEALING"]

# Solve a problem
result = await solve_problem(
    problem_type="QAOA",
    config={
        "type": "maxcut",
        "edges": [[0, 1], [1, 2], [2, 0]],
        "weights": [1, 1, 1]
    },
    parameters={
        "layers": 3,
        "optimizer": "COBYLA",
        "shots": 1000,
        "backend": "aer_simulator"
    }
)

if result.success:
    print(f"Solution: {result.data}")
else:
    print(f"Error: {result.error}")
```

### 3.2 Adding a New Problem Type

Create a new processor:

```python
# api/routers/jobs/processors/custom_processor.py
from api.routers.jobs.processors.registry import ProblemProcessor, JobResult

class GroverProcessor(ProblemProcessor):
    def get_problem_type(self) -> str:
        return "GROVER"
    
    async def validate_config(self, config: dict) -> tuple[bool, str | None]:
        if "oracle" not in config:
            return False, "Grover requires 'oracle' in config"
        return True, None
    
    async def solve(self, config: dict, parameters: dict) -> JobResult:
        try:
            # Your Grover implementation
            result = await run_grover_algorithm(config, parameters)
            return JobResult(success=True, data=result)
        except Exception as e:
            return JobResult(success=False, error=str(e))

# Register it
from api.routers.jobs.processors.registry import registry
registry.register(GroverProcessor())
```

That's it! The new problem type is now available without modifying any existing code.

---

## 4. Testing the Optimizations

### 4.1 Run Unit Tests

```bash
# Test optimized stores
pytest tests/unit/test_optimized_stores.py -v

# Expected output:
# test_email_exists_is_o1 .................. PASSED
# test_get_by_email_uses_index ............. PASSED
# test_get_by_id_uses_index ................ PASSED
# test_index_updated_on_save ............... PASSED
# test_index_cleaned_on_delete ............. PASSED
# test_count_is_o1 ......................... PASSED
```

### 4.2 Performance Benchmark

```python
# benchmarks/test_email_lookup.py
import asyncio
import time
from api.auth_stores import InMemoryUserStore

async def benchmark():
    store = InMemoryUserStore()
    
    # Add 10,000 users
    for i in range(10000):
        await store.save({
            "username": f"user{i}",
            "user_id": f"usr_{i:05d}",
            "email": f"user{i}@example.com",
            "password_hash": "hashed"
        })
    
    # Benchmark email check
    start = time.perf_counter()
    for _ in range(1000):
        await store.email_exists("user5000@example.com")
    elapsed = time.perf_counter() - start
    
    print(f"1,000 email checks with 10,000 users: {elapsed*1000:.2f}ms")
    print(f"Average per check: {elapsed:.6f}s = {elapsed*1000000:.2f}μs")

asyncio.run(benchmark())
```

**Expected output:**
```
1,000 email checks with 10,000 users: 15.23ms
Average per check: 0.000015s = 15.23μs
```

---

## 5. Monitoring & Observability

### 5.1 Health Check Endpoints

```bash
# Basic health (for load balancers)
curl http://localhost:8000/health

# Readiness check (for Kubernetes)
curl http://localhost:8000/health/ready

# Detailed health (for monitoring)
curl http://localhost:8000/health/detailed | jq

# Crypto-specific health
curl http://localhost:8000/health/crypto | jq
```

### 5.2 Cache Metrics

```bash
# Get cache statistics
curl http://localhost:8000/api/v1/cache/stats | jq

# Clear cache
curl -X POST http://localhost:8000/api/v1/cache/clear
```

### 5.3 Key Rotation Status

```python
from api.main import app

# Get key rotation status
status = app.state.key_rotation_service.get_status()
print(status)
```

Output:
```json
{
  "total_keys": 2,
  "active_keys": 1,
  "expiring_keys": 0,
  "scheduler_running": true,
  "policy": {
    "max_age_days": 90,
    "rotate_before_days": 7
  },
  "keys_by_type": {
    "kem": 0,
    "signing": 1
  }
}
```

---

## 6. Configuration Examples

### 6.1 Development Environment

```bash
# .env.development
APP_ENV=development
DEBUG=true

# Database (use SQLite for dev)
DATABASE_URL=sqlite+aiosqlite:///./data/qsop_dev.db

# Redis (optional for dev)
REDIS_URL=redis://localhost:6379/0

# Cache
RESULT_CACHE_ENABLED=true
RESULT_CACHE_TTL=60  # 1 minute for dev

# PQC Keys
PQC_KEY_MAX_AGE_DAYS=30       # Faster rotation for testing
PQC_KEY_ROTATE_BEFORE_DAYS=3

# Celery (disable for simple dev)
USE_CELERY=false

# Quantum Backend
QUANTUM_BACKEND=aer_simulator  # Use simulator, not real quantum hardware
```

### 6.2 Production Environment

```bash
# .env.production
APP_ENV=production
DEBUG=false

# Database (use PostgreSQL for production)
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/qsop

# Redis (required for production)
REDIS_URL=redis://redis:6379/0

# Cache
RESULT_CACHE_ENABLED=true
RESULT_CACHE_TTL=300  # 5 minutes

# PQC Keys
PQC_KEY_MAX_AGE_DAYS=90
PQC_KEY_ROTATE_BEFORE_DAYS=7

# Celery (required for production)
USE_CELERY=true
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Quantum Backend
QUANTUM_BACKEND=ibm_quantum  # Use real quantum hardware

# Monitoring
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
METRICS_ENABLED=true
```

---

## 7. Deployment

### 7.1 Docker Compose (Development)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f qsop

# Check health
curl http://localhost:8000/health
```

### 7.2 Production Deployment

```bash
# Build and deploy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check service status
docker-compose ps

# View metrics
open http://localhost:3000  # Grafana dashboard
```

---

## 8. Troubleshooting

### 8.1 Common Issues

**Issue:** "Email check still slow"  
**Solution:** Make sure you're using `InMemoryUserStore` with indexes, not a custom store without `email_exists()` method.

**Issue:** "Cache not working"  
**Solution:** Check Redis connection:
```bash
redis-cli ping  # Should return "PONG"
curl http://localhost:8000/api/v1/cache/stats  # Check if cache initialized
```

**Issue:** "Key rotation failed"  
**Solution:** Check logs:
```bash
docker-compose logs qsop | grep "key_rotation"
```

**Issue:** "Strategy pattern not used"  
**Solution:** Import from correct location:
```python
from api.routers.jobs.processors.registry import solve_problem
```

### 8.2 Debug Mode

Enable detailed logging:
```bash
LOG_LEVEL=DEBUG
LOG_FORMAT=json  # or "console" for human-readable
```

---

## 9. Performance Tips

### 9.1 Maximize Cache Hit Rate

1. **Use consistent parameter ordering** - JSON with sorted keys ensures identical problems hash the same
2. **Set appropriate TTL** - Balance freshness vs recomputation
3. **Monitor hit rate** - Aim for >50% hit rate

### 9.2 Optimize Database Queries

1. **Use indexed lookups** - `email_exists()`, `get_by_id()` are O(1)
2. **Avoid full scans** - Don't call `list(limit=10000)` just to count
3. **Use pagination** - Always use `limit` and `offset`

### 9.3 Memory Management

1. **Enable bounded stores** - Set `max_size` and `default_ttl`
2. **Monitor memory** - Use Grafana dashboards
3. **Configure eviction** - LRU policy works for most cases

---

## 10. Next Steps

1. ✅ Review this guide
2. ✅ Test the optimizations in development
3. ⏳ Implement remaining Phase 2 items (Celery default, bounded stores)
4. ⏳ Add missing tests (see `COMPREHENSIVE_IMPROVEMENT_PLAN.md`)
5. ⏳ Deploy to production with monitoring

---

**For detailed roadmap:** See `COMPREHENSIVE_IMPROVEMENT_PLAN.md`  
**For implementation details:** See `IMPLEMENTATION_SUMMARY.md`  
**For architecture:** See `AGENTS.md` and `README.md`
