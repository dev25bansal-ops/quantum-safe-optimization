"""
QSOP Client SDK Examples.

This module contains example usage patterns for the QSOP Python SDK.
"""

import asyncio
import os
from qsop_client import QSOPClient, SyncQSOPClient, QSOPClientError


async def example_basic_usage():
    """Basic async usage example."""
    async with QSOPClient(base_url="http://localhost:8000") as client:
        # Login
        await client.login("admin", os.getenv("ADMIN_PASSWORD", "admin123!"))

        # Get current user
        user = await client.get_current_user()
        print(f"Logged in as: {user.username}")

        # List existing jobs
        jobs = await client.get_jobs(limit=10)
        print(f"Found {len(jobs)} jobs")

        # Submit a QAOA MaxCut job
        job = await client.submit_job(
            problem_type="QAOA",
            problem_config={
                "type": "maxcut",
                "graph": {"edges": [[0, 1], [1, 2], [2, 0]], "weights": [1.0, 1.0, 1.0]},
            },
            parameters={"layers": 2, "shots": 1024, "optimizer": "COBYLA", "backend": "qiskit_aer"},
        )
        print(f"Submitted job: {job.id}")

        # Wait for completion
        job = await client.wait_for_job(job.id, timeout=300)

        if job.status == "completed" and job.result:
            print(f"Optimal value: {job.result.get('optimal_value')}")
        elif job.error:
            print(f"Job failed: {job.error}")


async def example_with_webhook():
    """Submit job with webhook notification."""
    async with QSOPClient() as client:
        await client.login("admin", "admin123!")

        job = await client.submit_job(
            problem_type="VQE",
            problem_config={
                "type": "molecular_hamiltonian",
                "molecule": "H2",
                "basis_set": "sto-3g",
            },
            parameters={
                "ansatz_type": "hardware_efficient",
                "shots": 4096,
                "backend": "qiskit_aer",
            },
            webhook_url="https://your-server.com/webhook/qsop",
        )
        print(f"Submitted with webhook: {job.id}")


async def example_key_management():
    """PQC key management example."""
    async with QSOPClient() as client:
        await client.login("admin", "admin123!")

        # Generate a new KEM key pair
        kem_key = await client.generate_key(key_type="kem", security_level=3)
        print(f"Generated KEM key: {kem_key.key_id}")
        print(f"Algorithm: {kem_key.algorithm}")

        # Generate a signing key pair
        signing_key = await client.generate_key(key_type="signing", security_level=3)
        print(f"Generated signing key: {signing_key.key_id}")

        # List all keys
        keys = await client.get_keys()
        for key in keys:
            print(f"  {key.key_type}: {key.key_id} ({key.algorithm})")


def example_sync_usage():
    """Synchronous usage example."""
    with SyncQSOPClient() as client:
        client.login("admin", "admin123!")

        # Submit job
        job = client.submit_job(
            problem_type="QAOA",
            problem_config={"type": "maxcut", "graph": {"edges": [[0, 1], [1, 2], [2, 0]]}},
        )
        print(f"Job submitted: {job.id}")

        # Wait for result
        job = client.wait_for_job(job.id)
        print(f"Job status: {job.status}")


async def example_error_handling():
    """Error handling example."""
    async with QSOPClient() as client:
        try:
            # Try to access protected endpoint without login
            await client.get_jobs()
        except QSOPClientError as e:
            print(f"Expected error: {e}")
            print(f"Status code: {e.status_code}")

        # Login and try invalid job ID
        await client.login("admin", "admin123!")

        try:
            await client.get_job("invalid-job-id")
        except QSOPClientError as e:
            if e.status_code == 404:
                print("Job not found (expected)")
            else:
                raise


async def example_health_check():
    """Health check example."""
    async with QSOPClient() as client:
        # Check API health
        health = await client.health_check()
        print(f"API Status: {health.get('status')}")

        # Check crypto provider
        crypto = await client.crypto_status()
        print(f"Crypto Implementation: {crypto.get('implementation')}")
        print(f"liboqs Available: {crypto.get('liboqs_available')}")
        if crypto.get("security_warning"):
            print(f"Warning: {crypto.get('security_warning')}")


async def example_batch_jobs():
    """Submit multiple jobs and track them."""
    async with QSOPClient() as client:
        await client.login("admin", "admin123!")

        # Submit multiple jobs
        jobs = []
        for i in range(5):
            job = await client.submit_job(
                problem_type="QAOA",
                problem_config={
                    "type": "maxcut",
                    "graph": {"edges": [[0, 1], [1, 2], [2, 3], [3, 0]]},
                },
                parameters={"layers": i + 1, "shots": 1000},
            )
            jobs.append(job)
            print(f"Submitted job {i + 1}: {job.id}")

        # Wait for all jobs concurrently
        async def wait_and_print(job_id: str):
            job = await client.wait_for_job(job_id)
            print(f"Job {job_id[:8]}... finished: {job.status}")

        await asyncio.gather(*[wait_and_print(job.id) for job in jobs])


if __name__ == "__main__":
    print("=== QSOP Client SDK Examples ===\n")

    print("1. Basic Usage:")
    asyncio.run(example_basic_usage())

    print("\n2. Sync Usage:")
    example_sync_usage()

    print("\n3. Health Check:")
    asyncio.run(example_health_check())

    print("\n4. Key Management:")
    asyncio.run(example_key_management())
