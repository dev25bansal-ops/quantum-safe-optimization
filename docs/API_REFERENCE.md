# Quantum-Safe Optimization Platform - API Reference

## Overview

This document provides comprehensive API reference documentation for the Quantum-Safe Optimization Platform.

**Base URL**: `http://localhost:8000`
**API Version**: `v1`
**API Prefix**: `/api/v1/`

---

## Authentication

All API endpoints require authentication using JWT tokens with PQC signatures.

### Authentication Header
```
Authorization: Bearer <jwt_token>
```

### Obtaining a Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "password": "your_password"
  }'
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

---

## Endpoints

### Health Check

#### GET `/health`
Check the health status of the API.

**Response**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "checks": {
    "database": "ok",
    "cache": "ok",
    "crypto": "ok"
  }
}
```

---

### Optimization Jobs

#### POST `/api/v1/jobs`
Submit a new optimization job.

**Request Body**:
```json
{
  "problem_type": "QAOA",
  "problem_config": {
    "problem": "maxcut",
    "edges": [[0, 1], [1, 2], [2, 0]],
    "weights": [1, 1, 1]
  },
  "parameters": {
    "layers": 3,
    "shots": 1000,
    "optimizer": "COBYLA"
  },
  "backend": "local_simulator",
  "priority": 5
}
```

**Response**:
```json
{
  "job_id": "job_12345",
  "status": "queued",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/v1/jobs`
List all jobs for the current user.

**Query Parameters**:
- `status` (optional): Filter by status
- `limit` (optional): Maximum results (default: 20)
- `offset` (optional): Pagination offset

**Response**:
```json
{
  "jobs": [
    {
      "job_id": "job_12345",
      "status": "completed",
      "problem_type": "QAOA",
      "created_at": "2024-01-15T10:30:00Z",
      "result": {
        "solution": [1, 0, 1],
        "energy": -2.5
      }
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

#### GET `/api/v1/jobs/{job_id}`
Get details of a specific job.

**Response**:
```json
{
  "job_id": "job_12345",
  "status": "completed",
  "problem_type": "QAOA",
  "backend": "local_simulator",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "completed_at": "2024-01-15T10:30:10Z",
  "result": {
    "solution": [1, 0, 1],
    "energy": -2.5,
    "iterations": 15
  }
}
```

#### DELETE `/api/v1/jobs/{job_id}`
Cancel or delete a job.

---

### Quantum Backends

#### GET `/api/v1/backends`
List available quantum backends.

**Response**:
```json
{
  "backends": [
    {
      "name": "local_simulator",
      "provider": "qiskit",
      "status": "available",
      "qubits": 32,
      "queue_length": 0
    },
    {
      "name": "ibm_quantum",
      "provider": "ibm",
      "status": "available",
      "qubits": 127,
      "queue_length": 5
    }
  ]
}
```

---

### Security & Keys

#### POST `/api/v1/security/keys`
Generate a new PQC key pair.

**Request Body**:
```json
{
  "key_type": "signing",
  "security_level": 3
}
```

**Response**:
```json
{
  "key_id": "key_12345",
  "public_key": "base64_encoded_public_key",
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-04-15T10:30:00Z"
}
```

#### GET `/api/v1/security/keys`
List all keys for the current user.

---

### Analytics

#### GET `/api/v1/analytics/usage`
Get usage statistics for the current user.

**Query Parameters**:
- `start_date`: Start date for statistics
- `end_date`: End date for statistics
- `granularity`: `hour`, `day`, `week`, `month`

**Response**:
```json
{
  "total_jobs": 150,
  "completed_jobs": 145,
  "failed_jobs": 5,
  "total_runtime_seconds": 3600,
  "by_problem_type": {
    "QAOA": 100,
    "VQE": 50
  }
}
```

---

## Error Responses

All errors follow a standard format:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_12345",
  "details": {
    "field": "additional information"
  }
}
```

### Common Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Invalid input data |
|