# QSOP Python SDK

A fully-typed async client library for the Quantum-Safe Optimization Platform API.

## Installation

```bash
pip install qsop-client
```

Or install from source:

```bash
cd qsop_client
pip install -e .
```

## Features

- ✅ **Full Type Hints** - IDE autocomplete and type checking
- ✅ **Async/Await** - Modern async API
- ✅ **Sync Wrapper** - For non-async applications
- ✅ **Automatic Token Management** - Login, refresh, logout
- ✅ **Retry Logic** - Exponential backoff for failed requests
- ✅ **Error Handling** - Typed exceptions with details
- ✅ **WebSocket Ready** - For real-time updates

## Quick Start

### Async Usage

```python
import asyncio
from qsop_client import QSOPClient

async def main():
    async with QSOPClient(base_url="http://localhost:8000") as client:
        # Login
        await client.login("admin", "password")

        # Submit a QAOA MaxCut job
        job = await client.submit_job(
            problem_type="QAOA",
            problem_config={
                "type": "maxcut",
                "graph": {"edges": [[0, 1], [1, 2], [2, 0]]}
            },
            parameters={"layers": 2, "shots": 1024}
        )

        # Wait for completion
        job = await client.wait_for_job(job.id, timeout=300)

        if job.result:
            print(f"Optimal value: {job.result.get('optimal_value')}")

asyncio.run(main())
```

### Synchronous Usage

```python
from qsop_client import SyncQSOPClient

with SyncQSOPClient() as client:
    client.login("admin", "password")

    job = client.submit_job(
        problem_type="QAOA",
        problem_config={"type": "maxcut", "graph": {"edges": [[0, 1]]}}
    )

    job = client.wait_for_job(job.id)
    print(f"Status: {job.status}")
```

## API Reference

### Authentication

```python
# Login
response = await client.login("username", "password")
# Returns: {"access_token": "...", "refresh_token": "...", "expires_in": 3600}

# Get current user
user = await client.get_current_user()
# Returns: User(user_id="...", username="...", roles=[...])

# Logout
await client.logout()
```

### Jobs

```python
# Submit job
job = await client.submit_job(
    problem_type="QAOA",  # or "VQE", "ANNEALING", "GROVER"
    problem_config={...},
    parameters={"layers": 2, "shots": 1024},
    webhook_url="https://..."  # optional
)

# Get job status
job = await client.get_job(job_id)

# List jobs
jobs = await client.get_jobs(status="running", limit=100)

# Cancel job
job = await client.cancel_job(job_id)

# Get result
result = await client.get_job_result(job_id)

# Wait for completion
job = await client.wait_for_job(job_id, timeout=300, poll_interval=2.0)
```

### Keys

```python
# Generate PQC key pair
key = await client.generate_key(key_type="kem", security_level=3)
# Returns: KeyPair(key_id="...", algorithm="ML-KEM-768", ...)

# List keys
keys = await client.get_keys()
```

### Health

```python
# API health
health = await client.health_check()
# Returns: {"status": "healthy", ...}

# Crypto status
crypto = await client.crypto_status()
# Returns: {"implementation": "liboqs", "liboqs_available": true, ...}
```

## Types

### JobStatus

```python
JobStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
```

### AlgorithmType

```python
AlgorithmType = Literal["QAOA", "VQE", "ANNEALING", "GROVER"]
```

### BackendType

```python
BackendType = Literal["qiskit_aer", "ibm_quantum", "aws_braket", "azure_quantum", "dwave_leap"]
```

## Error Handling

```python
from qsop_client import QSOPClientError

try:
    await client.get_job("invalid-id")
except QSOPClientError as e:
    print(f"Error: {e}")
    print(f"Status: {e.status_code}")
    print(f"Details: {e.details}")
```

## Examples

See `examples.py` for comprehensive examples:

- Basic usage
- Job submission with webhooks
- Key management
- Error handling
- Health checks
- Batch job submission

## Testing

```bash
# Run unit tests
pytest qsop_client/tests.py -v

# Run integration tests (requires API server)
pytest qsop_client/tests.py -v -m integration
```

## Requirements

- Python >= 3.11
- httpx >= 0.26.0

## License

MIT
