# API Migration Guide

## Overview

This guide helps migrate from deprecated root-level API endpoints to the versioned `/api/v1/` endpoints.

## Deprecated Endpoints

The following root-level endpoints are **deprecated** and will be removed in version 2.0.0:

| Deprecated Endpoint | New Endpoint      | Migration Deadline |
| ------------------- | ----------------- | ------------------ |
| `/auth/*`           | `/api/v1/auth/*`  | 2025-06-01         |
| `/jobs/*`           | `/api/v1/jobs/*`  | 2025-06-01         |
| `/ws`               | `/api/v1/ws`      | 2025-06-01         |
| `/costs/*`          | `/api/v1/costs/*` | 2025-06-01         |

## Migration Steps

### 1. Authentication Endpoints

**Before (Deprecated):**

```bash
POST /auth/login
POST /auth/register
POST /auth/refresh
POST /auth/logout
```

**After (Recommended):**

```bash
POST /api/v1/auth/login
POST /api/v1/auth/register
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
```

### 2. Job Endpoints

**Before (Deprecated):**

```bash
POST /jobs
GET /jobs/{job_id}
GET /jobs/{job_id}/result
DELETE /jobs/{job_id}
```

**After (Recommended):**

```bash
POST /api/v1/jobs
GET /api/v1/jobs/{job_id}
GET /api/v1/jobs/{job_id}/result
DELETE /api/v1/jobs/{job_id}
```

### 3. WebSocket Connection

**Before (Deprecated):**

```javascript
const ws = new WebSocket("wss://api.example.com/ws");
```

**After (Recommended):**

```javascript
const ws = new WebSocket("wss://api.example.com/api/v1/ws");
```

### 4. Cost Estimation

**Before (Deprecated):**

```bash
GET /costs/estimate
GET /costs/history
```

**After (Recommended):**

```bash
GET /api/v1/costs/estimate
GET /api/v1/costs/history
```

## Deprecation Timeline

| Phase          | Date       | Status   |
| -------------- | ---------- | -------- |
| Announcement   | 2024-01-01 | Complete |
| Warning Phase  | 2024-03-01 | Complete |
| Sunset Warning | 2025-01-01 | Active   |
| Removal        | 2025-06-01 | Planned  |

## Detection

During the warning phase, deprecated endpoints return:

```
X-Deprecated: true
X-Sunset: 2025-06-01
Link: </api/v1/auth/login>; rel="successor-version"
```

## Client Migration

### JavaScript/TypeScript

```javascript
// Before
const API_BASE = "";

// After
const API_BASE = "/api/v1";

// Usage
fetch(`${API_BASE}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username, password }),
});
```

### Python

```python
# Before
BASE_URL = "https://api.example.com"

# After
BASE_URL = "https://api.example.com/api/v1"

# Usage
response = requests.post(f"{BASE_URL}/auth/login", json={...})
```

### cURL

```bash
# Before
curl -X POST https://api.example.com/auth/login

# After
curl -X POST https://api.example.com/api/v1/auth/login
```

## New Features in v1

The `/api/v1/` endpoints include enhancements:

1. **GraphQL API**: Available at `/api/v1/graphql`
2. **Enhanced Security**: ML-based anomaly detection
3. **Better Error Responses**: RFC 7807 Problem Details
4. **Request Tracing**: Correlation IDs in all responses
5. **Rate Limiting Headers**: X-RateLimit-\* headers

## Backward Compatibility

During the deprecation period:

- Both old and new endpoints work identically
- Responses are identical in structure
- Authentication tokens work on both

## Support

For migration assistance:

- GitHub Issues: https://github.com/dev25bansal-ops/quantum-safe-optimization/issues
- Email: support@quantum-platform.example.com

## Changelog

- **2024-01-01**: v1 API announced, legacy endpoints deprecated
- **2024-03-01**: Warning headers added to deprecated endpoints
- **2025-01-01**: Sunset date announced
- **2025-06-01**: Legacy endpoints removed (planned)
