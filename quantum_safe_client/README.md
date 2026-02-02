# QuantumSafe Python Client SDK

A comprehensive Python SDK for interacting with the QuantumSafe Quantum Optimization Platform.

## Features

- 🔐 **Quantum-Safe Security**: Built with post-quantum cryptography in mind
- ⚡ **Async & Sync Support**: Both async and synchronous clients available
- 🔄 **Job Management**: Submit, monitor, cancel, and retrieve quantum jobs
- 💰 **Cost Estimation**: Estimate costs before running expensive quantum computations
- 🔌 **Multiple Backends**: Support for IBM Quantum, AWS Braket, Azure Quantum, and D-Wave

## Installation

```bash
pip install quantum-safe-client
```

Or install from source:

```bash
git clone https://github.com/quantumsafe/quantum-safe-client.git
cd quantum-safe-client
pip install -e .
```

## Quick Start

### Synchronous Usage

```python
from quantum_safe_client import QuantumSafeClient, JobStatus

# Create client
client = QuantumSafeClient(
    base_url="https://api.quantumsafe.io",
    api_key="your-api-key"
)

# Submit a QAOA job
job = client.submit_qaoa_job(
    problem={"Q": [[1, -1], [-1, 1]]},
    backend="ibm_quantum",
    p=2,
    shots=1000
)

print(f"Job submitted: {job.id}")

# Wait for completion
result = client.wait_for_job(job.id, timeout=300)

if result.status == JobStatus.COMPLETED:
    print(f"Optimal solution: {result.result}")
else:
    print(f"Job failed: {result.error}")

client.close()
```

### Async Usage

```python
import asyncio
from quantum_safe_client import AsyncQuantumSafeClient, JobStatus

async def run_optimization():
    async with AsyncQuantumSafeClient(
        base_url="https://api.quantumsafe.io",
        api_key="your-api-key"
    ) as client:
        # Submit job
        job = await client.submit_qaoa_job(
            problem={"Q": [[1, -1], [-1, 1]]},
            backend="simulator",
            p=2,
            shots=1000
        )
        
        # Wait for result
        result = await client.wait_for_job(job.id, timeout=300)
        return result

result = asyncio.run(run_optimization())
print(result.result)
```

### Context Manager Usage

```python
from quantum_safe_client import QuantumSafeClient

with QuantumSafeClient(base_url="http://localhost:8000") as client:
    # Login
    client.login("username", "password")
    
    # List jobs
    jobs = client.list_jobs(status="completed", limit=10)
    for job in jobs:
        print(f"{job.id}: {job.status}")
```

## API Reference

### QuantumSafeClient / AsyncQuantumSafeClient

#### Authentication

```python
# Login with credentials
token = client.login(username, password)

# Refresh token
new_token = client.refresh_token()
```

#### Job Submission

```python
# QAOA Job
job = client.submit_qaoa_job(
    problem={"Q": qubo_matrix},
    backend="ibm_quantum",
    p=2,                    # QAOA layers
    shots=1000,             # Measurement shots
    optimizer="COBYLA",     # Classical optimizer
    webhook_url="https://..."  # Optional callback
)

# VQE Job
job = client.submit_vqe_job(
    hamiltonian={"terms": [...]},
    ansatz="uccsd",
    backend="simulator",
    shots=1000
)

# Quantum Annealing Job
job = client.submit_annealing_job(
    problem={"Q": qubo_matrix},
    backend="dwave",
    num_reads=1000,
    annealing_time=20
)
```

#### Job Management

```python
# Get job status
job = client.get_job("job-id-123")

# List jobs
jobs = client.list_jobs(status="running", limit=50)

# Cancel job
cancelled = client.cancel_job("job-id-123", reason="User requested")

# Delete job
client.delete_job("job-id-123")

# Wait for completion
result = client.wait_for_job("job-id-123", poll_interval=2.0, timeout=300)
```

#### Cost Estimation

```python
estimate = client.estimate_cost(
    job_type="qaoa",
    backend="ibm_quantum",
    shots=10000,
    circuit_depth=50,
    num_qubits=20
)

print(f"Estimated cost: ${estimate.estimated_cost_usd:.2f}")
print(f"Estimated time: {estimate.estimated_time_seconds}s")
```

#### Backend Information

```python
# List available backends
backends = client.list_backends()
for backend in backends:
    print(f"{backend.name}: {backend.num_qubits} qubits, {backend.status}")

# Get backend status
status = client.get_backend_status("ibm_brisbane")
```

## Models

### Job

```python
from quantum_safe_client import Job, JobStatus, JobType

job.id              # Unique identifier
job.job_type        # JobType.QAOA, JobType.VQE, JobType.ANNEALING
job.status          # JobStatus.PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
job.backend         # Backend name
job.progress        # 0-100
job.result          # Results dict (when completed)
job.error           # Error message (when failed)
job.duration        # Execution time in seconds

# Helper properties
job.is_complete     # True if finished
job.is_successful   # True if completed successfully
```

### CostEstimate

```python
estimate.backend              # Target backend
estimate.estimated_cost_usd   # Cost in USD
estimate.estimated_time_seconds  # Execution time
estimate.breakdown            # Detailed cost breakdown
```

### QuantumBackend

```python
backend.name         # Backend identifier
backend.provider     # IBM, AWS, D-Wave, etc.
backend.num_qubits   # Available qubits
backend.status       # online/offline
backend.is_available # True if accepting jobs
```

## Exception Handling

```python
from quantum_safe_client import (
    QuantumSafeError,
    AuthenticationError,
    JobNotFoundError,
    ValidationError,
    RateLimitError,
    APIError,
)

try:
    job = client.get_job("invalid-id")
except JobNotFoundError:
    print("Job not found")
except AuthenticationError:
    print("Please login first")
except RateLimitError:
    print("Too many requests, please wait")
except APIError as e:
    print(f"API error: {e}")
```

## Configuration

### Environment Variables

```bash
export QUANTUMSAFE_API_URL="https://api.quantumsafe.io"
export QUANTUMSAFE_API_KEY="your-api-key"
```

### Client Options

```python
client = QuantumSafeClient(
    base_url="https://api.quantumsafe.io",
    api_key="your-api-key",      # API key auth
    token="jwt-token",           # Or JWT token
    timeout=60.0,                # Request timeout
    verify_ssl=True,             # SSL verification
)
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black quantum_safe_client/

# Type checking
mypy quantum_safe_client/

# Linting
ruff check quantum_safe_client/
```

## License

MIT License - see [LICENSE](LICENSE) for details.
