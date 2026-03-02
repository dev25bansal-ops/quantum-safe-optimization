# QSOP API Documentation

**QSOP (Quantum-Safe Secure Optimization Platform) API Reference**

This is the official API documentation for QSOP, a production-ready quantum-safe secure optimization platform that integrates post-quantum cryptographic schemes with quantum and classical optimization algorithms.

## Base URL

```
https://api.qsop.example.com/v1
```

## Authentication

QSOP uses ML-DSA (Module-Lattice-based Digital Signature Algorithm) for API authentication. All requests must include a valid PQC (Post-Quantum Cryptography) token in the `Authorization` header.

### Authentication Header

```
Authorization: PQC <token>
```

### Obtaining a Token

Authentication tokens are obtained using post-quantum key exchange (ML-KEM) with your registered public key.

```python
from qsop.client import QSOPClient

client = QSOPClient(
    tenant_id="your-tenant-id",
    private_key_path="/path/to/your/private_key.pem"
)

# Token is automatically handled by the client
token = client.authenticate()
```

### Token Example

```
PQC eyJhbGciOiJtZC1kc2EtNjUiLCJ0eXAiOiJKV1QifQ.eyJ0ZW5hbnRfaWQiOiJhYmMxMjMiLCJleHAiOjE3MDUzMDQ2MDB9.sphincs_signature_here
```

## Error Responses

All endpoints return RFC 7807 Problem Details error responses.

### Common Error Types

| Type | HTTP Status | Description |
|------|-------------|-------------|
| `https://api.qsop.example.com/errors/validation-error` | 422 | Invalid request parameters |
| `https://api.qsop.example.com/errors/authentication-error` | 401 | Authentication failed |
| `https://api.qsop.example.com/errors/not-found` | 404 | Resource not found |
| `https://api.qsop.example.com/errors/conflict` | 409 | Resource state conflict |
| `https://api.qsop.example.com/errors/rate-limit-exceeded` | 429 | Rate limit exceeded |
| `https://api.qsop.example.com/errors/internal-error` | 500 | Internal server error |

### Error Response Format

```json
{
  "type": "https://api.qsop.example.com/errors/not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "Job with ID '550e8400-e29b-41d4-a716-446655440000' not found",
  "instance": "https://api.qsop.example.com/jobs/550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123xyz",
  "errors": []
}
```

---

## Jobs

### Submit a Job

Submit a new optimization job to the platform.

**Endpoint:** `POST /jobs`

**Request Body:** `JobCreate`

#### Example: QAOA MaxCut

```json
POST /v1/jobs
Authorization: PQC <token>
Content-Type: application/json

{
  "algorithm": "qaoa",
  "backend": "qiskit_aer",
  "parameters": {
    "p": 2,
    "optimizer": "COBYLA",
    "max_iterations": 100
  },
  "problem_config": {
    "type": "qaoa_maxcut",
    "graph": {
      "nodes": 4,
      "edges": [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]
    },
    "weighted": false
  },
  "crypto": {
    "kem_algorithm": "kyber768",
    "sig_algorithm": "dilithium3",
    "hybrid_mode": true,
    "enabled": true
  },
  "name": "MaxCut-4Nodes-Trial1",
  "priority": 5,
  "callback_url": "https://example.com/webhooks/job-complete"
}
```

#### Example: VQE Molecular Hamiltonian (H₂)

```json
POST /v1/jobs
Authorization: PQC <token>
Content-Type: application/json

{
  "algorithm": "vqe",
  "backend": "qiskit_aer",
  "parameters": {
    "ansatz": "UCCSD",
    "optimizer": "SPSA",
    "max_iterations": 200
  },
  "problem_config": {
    "type": "vqe_molecular_hamiltonian",
    "molecule": "H2",
    "basis": "sto-3g",
    "geometry": [
      [0.0, 0.0, 0.0],
      [0.0, 0.0, 0.735]
    ],
    "charge": 0,
    "spin": 0
  },
  "crypto": {
    "kem_algorithm": "kyber768",
    "sig_algorithm": "dilithium3",
    "hybrid_mode": true,
    "enabled": true
  },
  "name": "H2-VQE-Energy-Calc",
  "priority": 8
}
```

#### Example: Quantum Annealing QUBO

```json
POST /v1/jobs
Authorization: PQC <token>
Content-Type: application/json

{
  "algorithm": "quantum_annealing",
  "backend": "dwave",
  "parameters": {
    "anneal_time": 1000,
    "num_reads": 1000
  },
  "problem_config": {
    "type": "annealing_qubo",
    "q_matrix": [
      [1.0, -0.5, 0.0],
      [-0.5, 1.0, -0.5],
      [0.0, -0.5, 1.0]
    ],
    "num_qubits": 3,
    "offset": 0.0
  },
  "crypto": {
    "kem_algorithm": "kyber768",
    "sig_algorithm": "dilithium3",
    "hybrid_mode": true,
    "enabled": true
  },
  "name": "QUBO-3Vars-Optimization",
  "priority": 7
}
```

**Response:** `JobResponse` - 201 Created

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "tenant-123",
  "name": "MaxCut-4Nodes-Trial1",
  "algorithm": "qaoa",
  "backend": "qiskit_aer",
  "parameters": {
    "p": 2,
    "optimizer": "COBYLA",
    "max_iterations": 100
  },
  "status": "queued",
  "priority": 5,
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": null,
  "completed_at": null,
  "error_message": null,
  "progress": null,
  "estimated_completion": null
}
```

---

### List Jobs

List all jobs for the current tenant with optional filtering.

**Endpoint:** `GET /jobs`

**Query Parameters:**
- `status` (optional): Filter by job status (`pending`, `queued`, `running`, `completed`, `failed`, `cancelled`)
- `limit` (optional): Maximum number of results (default: 20, max: 100)
- `offset` (optional): Number of results to skip (default: 0)

**Example Request:**

```bash
GET /v1/jobs?status=completed&limit=10&offset=0
Authorization: PQC <token>
```

**Response:** `JobListResponse`

```json
{
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "tenant_id": "tenant-123",
      "name": "MaxCut-4Nodes-Trial1",
      "algorithm": "qaoa",
      "backend": "qiskit_aer",
      "parameters": {
        "p": 2,
        "optimizer": "COBYLA"
      },
      "status": "completed",
      "priority": 5,
      "created_at": "2024-01-15T10:30:00Z",
      "started_at": "2024-01-15T10:30:05Z",
      "completed_at": "2024-01-15T10:30:45Z",
      "error_message": null,
      "progress": 100.0
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

---

### Get Job Details

Get details of a specific job. For completed jobs, use `include_results=true` to automatically include results.

**Endpoint:** `GET /jobs/{job_id}`

**Query Parameters:**
- `include_results` (optional): Include results for completed jobs (default: `false`)

**Example Request:**

```bash
GET /v1/jobs/550e8400-e29b-41d4-a716-446655440000
Authorization: PQC <token>
```

**Response:** `JobResponse` or `JobResultsResponse`

---

### Cancel a Job

Cancel a running or queued job.

**Endpoint:** `DELETE /jobs/{job_id}`

**Example Request:**

```bash
DELETE /v1/jobs/550e8400-e29b-41d4-a716-446655440000
Authorization: PQC <token>
```

**Response:** 204 No Content

---

## Algorithms

### List Algorithms

List all available quantum optimization algorithms.

**Endpoint:** `GET /algorithms`

**Example Request:**

```bash
GET /v1/algorithms
Authorization: PQC <token>
```

**Response:**

```json
{
  "algorithms": [
    {
      "name": "qaoa",
      "display_name": "QAOA",
      "description": "Quantum Approximate Optimization Algorithm for combinatorial optimization",
      "category": "optimization",
      "supported_backends": ["qiskit_aer", "ibm_quantum", "ionq"],
      "parameters": {
        "p": {
          "type": "integer",
          "min": 1,
          "max": 10,
          "default": 1,
          "description": "Number of QAOA layers"
        },
        "optimizer": {
          "type": "string",
          "options": ["COBYLA", "SPSA", "ADAM"],
          "default": "COBYLA"
        },
        "max_iterations": {
          "type": "integer",
          "min": 1,
          "max": 1000,
          "default": 100
        }
      },
      "version": "1.0.0"
    },
    {
      "name": "vqe",
      "display_name": "VQE",
      "description": "Variational Quantum Eigensolver for finding ground state energies",
      "category": "chemistry",
      "supported_backends": ["qiskit_aer", "ibm_quantum", "ionq"],
      "parameters": {
        "ansatz": {
          "type": "string",
          "options": ["RY", "UCCSD", "HEA"],
          "default": "RY"
        },
        "optimizer": {
          "type": "string",
          "options": ["COBYLA", "SPSA", "L-BFGS-B"],
          "default": "COBYLA"
        },
        "max_iterations": {
          "type": "integer",
          "min": 1,
          "max": 1000,
          "default": 100
        }
      },
      "version": "1.0.0"
    }
  ],
  "total": 2
}
```

---

### Get Algorithm Details

Get detailed information about a specific algorithm.

**Endpoint:** `GET /algorithms/{name}`

**Example Request:**

```bash
GET /v1/algorithms/qaoa
Authorization: PQC <token>
```

**Response:** `AlgorithmInfo`

---

## Backends

### List Backends

List all available quantum backends.

**Endpoint:** `GET /backends`

**Example Request:**

```bash
GET /v1/backends
Authorization: PQC <token>
```

**Response:**

```json
{
  "backends": [
    {
      "name": "qiskit_aer",
      "display_name": "Qiskit Aer Simulator",
      "provider": "local",
      "backend_type": "simulator",
      "qubits": 32,
      "status": "online",
      "description": "High-performance local quantum simulator"
    },
    {
      "name": "ibm_quantum",
      "display_name": "IBM Quantum",
      "provider": "ibm",
      "backend_type": "hardware",
      "qubits": 127,
      "status": "online",
      "description": "IBM quantum hardware via Qiskit Runtime"
    }
  ],
  "total": 2
}
```

---

### Get Backend Details

Get detailed information about a specific backend.

**Endpoint:** `GET /backends/{name}`

**Example Request:**

```bash
GET /v1/backends/qiskit_aer
Authorization: PQC <token>
```

**Response:** `BackendInfo`

---

## Cryptographic Keys

### Create Key

Create a new quantum-safe cryptographic key pair.

**Endpoint:** `POST /keys`

**Request Body:** `KeyCreate`

**Example Request:**

```json
POST /v1/keys
Authorization: PQC <token>
Content-Type: application/json

{
  "name": "production-encryption-key",
  "algorithm": "kyber768",
  "expires_in_days": 365,
  "auto_rotate": true,
  "rotation_period_days": 90,
  "metadata": {
    "environment": "production",
    "purpose": "job-protection"
  }
}
```

**Response:** `KeyResponse` - 201 Created

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440001",
  "name": "production-encryption-key",
  "algorithm": "kyber768",
  "key_size": 768,
  "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBCgKCAQEA...",
  "status": "active",
  "version": 1,
  "created_at": "2024-01-01T00:00:00Z",
  "rotated_at": null,
  "expires_at": "2025-01-01T00:00:00Z",
  "last_used_at": "2024-01-15T10:30:00Z",
  "usage_count": 42
}
```

---

### List Keys

List all cryptographic keys for the current tenant.

**Endpoint:** `GET /keys`

**Query Parameters:**
- `status` (optional): Filter by key status (`active`, `inactive`, `pending_rotation`, `revoked`, `expired`)
- `limit` (optional): Maximum number of results (default: 20, max: 100)
- `offset` (optional): Number of results to skip (default: 0)

**Response:** `KeyListResponse`

---

### Get Key Details

Get details of a specific key.

**Endpoint:** `GET /keys/{key_id}`

**Response:** `KeyResponse`

---

### Rotate Key

Rotate a cryptographic key, creating a new version while maintaining backward compatibility.

**Endpoint:** `POST /keys/{key_id}/rotate`

**Response:** `KeyRotateResponse`

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440001",
  "name": "production-encryption-key",
  "old_version": 1,
  "new_version": 2,
  "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBCgKCAQEA...",
  "rotated_at": "2024-04-01T00:00:00Z"
}
```

---

### Revoke Key

Revoke a cryptographic key.

**Endpoint:** `DELETE /keys/{key_id}`

**Response:** 204 No Content

---

## Workers

### List Workers

List all available worker nodes.

**Endpoint:** `GET /workers`

**Query Parameters:**
- `status` (optional): Filter by worker status (`idle`, `busy`, `offline`, `maintenance`)
- `backend_type` (optional): Filter by backend type (`simulator`, `hardware`)

**Example Request:**

```bash
GET /v1/workers?status=busy
Authorization: PQC <token>
```

**Response:**

```json
{
  "workers": [
    {
      "worker_id": "worker-01",
      "hostname": "qnode-01.quantum.local",
      "status": "busy",
      "backend_type": "simulator",
      "capabilities": ["qaoa", "vqe", "grover"],
      "current_job_id": "550e8400-e29b-41d4-a716-446655440000",
      "jobs_completed": 1250,
      "jobs_failed": 3,
      "uptime_seconds": 86400.0,
      "last_heartbeat": "2024-01-15T10:30:00Z",
      "cpu_usage": 45.5,
      "memory_usage": 62.3
    }
  ],
  "total": 5,
  "active": 3,
  "idle": 2
}
```

---

### Get Worker Details

Get detailed information about a specific worker.

**Endpoint:** `GET /workers/{worker_id}`

**Response:** `WorkerInfo`

---

### Drain Worker

Drain a worker node (stop accepting new jobs after current ones complete).

**Endpoint:** `POST /workers/{worker_id}/drain`

**Response:** 204 No Content

---

### Restart Worker

Gracefully restart a worker node.

**Endpoint:** `POST /workers/{worker_id}/restart`

**Response:** 204 No Content

---

## Webhooks

### Get Webhook Statistics

Get webhook delivery statistics.

**Endpoint:** `GET /webhooks/stats`

**Query Parameters:**
- `hours` (optional): Time range in hours (default: 24, max: 168)
- `webhook_id` (optional): Filter by specific webhook

**Example Request:**

```bash
GET /v1/webhooks/stats?hours=24
Authorization: PQC <token>
```

**Response:**

```json
{
  "summary": {
    "total_webhooks": 15,
    "active_webhooks": 12,
    "successful_deliveries_24h": 1425,
    "failed_deliveries_24h": 12,
    "avg_delivery_time_ms": 245.5,
    "success_rate_24h": 0.9917
  },
  "webhook_stats": [
    {
      "webhook_id": "webhook-123",
      "webhook_name": "Job Completion Callback",
      "total_attempts": 1500,
      "successful_attempts": 1485,
      "failed_attempts": 15,
      "average_response_time_ms": 234.5,
      "last_success_at": "2024-01-15T10:28:00Z",
      "last_failure_at": "2024-01-15T09:45:00Z",
      "status_code_distribution": {
        "200": 1485,
        "500": 10,
        "502": 5
      }
    }
  ],
  "recent_errors": [
    {
      "error_id": "err-456",
      "webhook_id": "webhook-123",
      "error_type": "ConnectionError",
      "error_message": "Connection timeout after 30 seconds",
      "status_code": null,
      "response_body": null,
      "timestamp": "2024-01-15T09:45:00Z",
      "retry_count": 2,
      "will_retry": true
    }
  ],
  "time_range_hours": 24
}
```

---

### Get Webhook Stats by ID

Get statistics for a specific webhook.

**Endpoint:** `GET /webhooks/{webhook_id}`

**Response:** `WebhookAttemptSummary`

---

### Get Webhook Errors

Get recent errors for a specific webhook.

**Endpoint:** `GET /webhooks/{webhook_id}/errors`

**Query Parameters:**
- `limit` (optional): Maximum number of errors (default: 20, max: 100)

**Response:** `WebhookErrorDetail[]`

---

## Client-Side Decryption

Results are encrypted using ML-KEM (Key Encapsulation Mechanism) and signed with ML-DSA (Digital Signature Algorithm). To decrypt results client-side:

```python
from qsop.client import QSOPClient
import json

# Initialize client with your private key
client = QSOPClient(
    tenant_id="your-tenant-id",
    private_key_path="/path/to/your/private_key.pem"
)

# Get job results
job_id = "550e8400-e29b-41d4-a716-446655440000"
results = client.get_job_results(job_id)

# Decrypt results
decrypted_results = client.decrypt_results(
    ciphertext=results["ciphertext"],
    signature=results["signature"],
    public_key=results["public_key"]
)

# Verify signature
if client.verify_results(decrypted_results, results["signature"], results["public_key"]):
    print("Results verified and decrypted successfully:")
    print(json.dumps(decrypted_results, indent=2))
else:
    print("Signature verification failed!")
```

---

## Credential Management

For production deployments, credentials should be managed using HashiCorp Vault or Azure Key Vault.

### Azure Key Vault Setup

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from qsop.clients import QSOPClient

# Configure Azure Key Vault
vault_url = "https://your-vault.vault.azure.net/"
credential = DefaultAzureCredential()
secret_client = SecretClient(vault_url=vault_url, credential=credential)

# Retrieve private key from Key Vault
private_key_secret = secret_client.get_secret("qsop-private-key")
private_key_bytes = base64.b64decode(private_key_secret.value)

# Initialize QSOP client with Key Vault credentials
client = QSOPClient(
    tenant_id="your-tenant-id",
    private_key=private_key_bytes
)
```

---