# ADR-0002: Use FastAPI as Primary Web Framework

## Status

Accepted

## Context

We need a modern web framework for building the quantum-safe optimization API. Requirements:

- Async support for handling concurrent quantum jobs
- Automatic OpenAPI documentation
- Type safety with Pydantic
- WebSocket support for real-time updates
- Good performance characteristics

## Decision

We selected **FastAPI** as our primary web framework.

## Rationale

| Criteria      | FastAPI     | Flask      | Django      | Express       |
| ------------- | ----------- | ---------- | ----------- | ------------- |
| Async Support | ✅ Native   | ❌ Limited | ✅ 3.1+     | ✅ Native     |
| Type Safety   | ✅ Pydantic | ❌ Manual  | ⚠️ Partial  | ⚠️ TypeScript |
| OpenAPI       | ✅ Auto     | ❌ Manual  | ❌ Manual   | ⚠️ Swagger    |
| Performance   | ⭐⭐⭐⭐⭐  | ⭐⭐⭐     | ⭐⭐⭐      | ⭐⭐⭐⭐      |
| WebSocket     | ✅ Native   | ❌ Addon   | ⚠️ Channels | ✅ Native     |

## Consequences

### Positive

- Automatic API documentation (Swagger UI, ReDoc)
- Request/response validation with Pydantic
- Excellent async/await support
- Dependency injection system for clean architecture
- Strong typing throughout the stack

### Negative

- Newer framework with smaller ecosystem than Django
- Learning curve for async patterns
- Some middleware compatibility issues

## Implementation

```python
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI()

class JobRequest(BaseModel):
    algorithm: str
    parameters: dict

@app.post("/jobs")
async def create_job(request: JobRequest):
    # Type-safe, validated, auto-documented
    pass
```

## Alternatives Considered

- **Flask**: Too limited for async operations
- **Django**: Too heavy, async support is newer
- **Starlette**: Considered (FastAPI is built on it), but FastAPI provides more

## Date

2024-01-01
