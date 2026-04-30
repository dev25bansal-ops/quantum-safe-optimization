# ADR-0003: Implement GraphQL API Alongside REST

## Status

Accepted

## Context

Our REST API works well for simple operations, but clients often need to:

- Fetch related data in single requests
- Query specific fields to reduce payload size
- Handle complex nested data structures

## Decision

We implemented a **GraphQL API** using Strawberry alongside our REST API.

## Rationale

| Use Case        | REST                 | GraphQL           |
| --------------- | -------------------- | ----------------- |
| Simple CRUD     | ✅ Optimal           | ⚠️ Overhead       |
| Complex Queries | ⚠️ Multiple requests | ✅ Single request |
| Field Selection | ❌ Fixed response    | ✅ Client selects |
| Real-time       | ⚠️ Polling           | ✅ Subscriptions  |
| Caching         | ✅ HTTP cache        | ⚠️ Complex        |

## Consequences

### Positive

- Reduced over-fetching and under-fetching
- Single request for complex queries
- Strong typing with schema
- Better frontend developer experience

### Negative

- Additional complexity
- Different error handling
- Caching challenges
- Learning curve for new team members

## Implementation

```python
import strawberry
from strawberry.fastapi import GraphQLRouter

@strawberry.type
class Query:
    @strawberry.field
    async def job(self, job_id: str) -> Optional[Job]:
        return await get_job(job_id)

schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)
```

## Usage

```graphql
query GetJobWithBackend {
  job(jobId: "job_abc123") {
    id
    status
    backend {
      name
      provider
    }
  }
}
```

## Guidelines

- Use **REST** for: Simple CRUD, file uploads, cached endpoints
- Use **GraphQL** for: Complex queries, dashboard data, mobile apps

## Date

2024-03-01
