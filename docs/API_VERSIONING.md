# API Versioning Policy

## Current Version

The current stable API version is **v1** (`/api/v1/`).

## Versioning Strategy

This API uses **URL path versioning**:

```
/api/v1/auth/login
/api/v1/jobs
/api/v1/jobs/{job_id}
/api/v1/metrics
```

### Why URL Path Versioning?

| Strategy | Pros | Cons | Chosen? |
|---|---|---|---|
| URL path (`/api/v1/`) | Simple, explicit, cacheable, widely understood | Version in every URL | Yes |
| Header versioning | Clean URLs | Harder to debug, cache issues | No |
| Query parameter | Easy to test | Pollutes query string, cache issues | No |
| Content negotiation | RESTful | Complex, poor tool support | No |

## Backward Compatibility

### Breaking Changes

A **breaking change** requires a new major version (v2):

- Removing an endpoint or field
- Changing a field's type or semantics
- Adding required request fields
- Changing authentication requirements
- Modifying error response formats

### Non-Breaking Changes

These changes are made within the current version:

- Adding new endpoints
- Adding optional request fields
- Adding new response fields
- Adding new query parameters
- Improving error messages (same status code)

## Deprecation Policy

When an API version is deprecated:

1. **Announcement**: Deprecation notice in release notes and `Deprecation` HTTP header
2. **Grace period**: Minimum 6 months before removal
3. **Sunset header**: `Sunset: <date>` header indicating when the version will be removed
4. **Migration guide**: Documentation for migrating to the new version

### Deprecation Timeline

| Version | Released | Deprecated | Sunset | Status |
|---|---|---|---|---|
| v1 | 2026-05 | — | — | **Current** |
| (legacy root routes) | — | 2026-05 | 2026-11 | **Removed** |

## Removed Routes

The following root-level routes were removed in May 2026 as part of Phase 2 bug fixes:

| Old Route | New Route | Migration |
|---|---|---|
| `POST /auth/login` | `POST /api/v1/auth/login` | Prefix with `/api/v1` |
| `POST /auth/register` | `POST /api/v1/auth/register` | Prefix with `/api/v1` |
| `GET /auth/me` | `GET /api/v1/auth/me` | Prefix with `/api/v1` |
| `POST /jobs` | `POST /api/v1/jobs` | Prefix with `/api/v1` |
| `GET /jobs/{id}` | `GET /api/v1/jobs/{id}` | Prefix with `/api/v1` |
| `GET /ws/{job_id}` | `GET /api/v1/ws/{job_id}` | Prefix with `/api/v1` |
| `GET /costs/estimate` | `GET /api/v1/costs/estimate` | Prefix with `/api/v1` |

These routes were duplicated at both root and `/api/v1/` level, doubling the attack surface and creating maintenance burden. The root-level versions have been removed. The `/api/v1/` versions remain unchanged.

## Client Compatibility

### OpenAPI Spec

The OpenAPI specification at `/openapi.json` always reflects the current API version. Clients should:

1. Generate client code from the OpenAPI spec using `scripts/generate_clients.py`
2. Pin client versions alongside API versions
3. Test against the staging environment before upgrading

### SDK Versioning

Generated SDKs follow semantic versioning:

- **Major version bump** when the API version changes
- **Minor version bump** for new endpoints or optional fields
- **Patch version bump** for bug fixes

## API Changes Log

| Date | Change | Impact |
|---|---|---|
| 2026-05-12 | Removed duplicate root-level routers | Breaking for clients using `/auth/`, `/jobs/` without `/api/v1/` prefix |
| 2026-05-12 | Added `/api/v1/auth/register` endpoint | New feature |
| 2026-05-12 | Added quota management endpoints | New feature |
| 2026-05-12 | Added problem auto-selector endpoint | New feature |
