# ADR-002: Database Abstraction — Cosmos DB vs PostgreSQL

**Status**: Accepted
**Date**: 2026-05-12
**Context**: Infrastructure & CI/CD (Phase 7)

## Decision

The project supports two database backends through an abstracted interface:

1. **Azure Cosmos DB** — Primary/default database for Azure deployments
2. **PostgreSQL** — Alternative for non-Azure, self-hosted, or cost-sensitive deployments

Both are accessed through a common interface defined in `api/db/`.

## Rationale

### Why support both?

1. **Vendor lock-in risk**: Cosmos DB ties the project to Azure. PostgreSQL enables deployment anywhere
2. **Cost**: Cosmos DB can be expensive for small deployments or development environments
3. **Developer experience**: PostgreSQL with `docker-compose up` is simpler than setting up Cosmos DB emulator
4. **Community adoption**: PostgreSQL is more familiar to most developers

### Implementation approach

- `api/db/postgres.py` — `PostgresManager` with async SQLAlchemy engine, session factory, and ORM models
- `api/db/cosmos.py` — Existing Cosmos DB manager (unchanged primary interface)
- Config selection via `DATABASE_TYPE` env var (`cosmos` | `postgres`)

### Why not a full repository pattern?

A full repository abstraction layer would add significant complexity for a codebase that primarily uses simple CRUD operations. Instead:

- Job storage uses the existing `JobStore` interface (`api/stores/`)
- User/auth data uses direct database access through the selected backend
- Each backend has its own manager class with a common interface

## Consequences

### Positive
- Deployable on Azure or any cloud/on-prem environment
- Lower barrier to entry for developers (PostgreSQL via Docker)
- Cost flexibility for different deployment scales

### Negative
- Two code paths to maintain and test
- Some database-specific features (Cosmos DB partitioning, PostgreSQL indexes) require separate optimization

## Data Models

### PostgreSQL (SQLAlchemy ORM)

```python
JobModel      # jobs table — id, user_id, status, problem_type, result, created_at, updated_at
UserModel     # users table — id, email, hashed_password, role, pqc_public_key, created_at
AuditLogModel # audit_logs table — id, user_id, action, details, timestamp
```

### Cosmos DB (Document)

Same logical model stored as JSON documents with partition keys.

## Alternatives Considered

| Alternative | Rejected Because |
|---|---|
| Cosmos DB only | Vendor lock-in, higher cost, harder local development |
| PostgreSQL only | Loses Azure native integration benefits for existing Azure deployments |
| Full repository pattern | Over-engineering for current CRUD needs |
| MongoDB | Less mature async driver, team already has PostgreSQL expertise |
