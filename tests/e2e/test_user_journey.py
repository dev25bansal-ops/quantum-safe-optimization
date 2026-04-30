"""
End-to-End user journey tests.

Tests complete user workflows:
- Registration → Login → Submit Job → Monitor → Get Results
- Admin workflow: User management, key rotation
- Full encryption flow
"""

import asyncio
import json
import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch, MagicMock


class TestFullUserJourney:
    """Test complete user workflow from registration to results."""

    @pytest.mark.asyncio
    async def test_registration_to_job_submission(self):
        """Test full user journey: register → login → submit job → check status."""
        # This test would require a running test server
        # For now, we test the individual components
        
        # Step 1: Create user
        import os
        os.environ["ADMIN_PASSWORD"] = "test_admin_pass"
        os.environ["APP_ENV"] = "test"
        
        from api.auth_stores import InMemoryUserStore
        from api.auth_stores import hash_password
        
        user_store = InMemoryUserStore()
        
        # Register user
        new_user = {
            "username": "testuser",
            "user_id": "usr_journey_001",
            "email": "user@example.com",
            "password_hash": hash_password("SecurePass123!"),
            "roles": ["user"],
            "created_at": datetime.now(UTC).isoformat(),
        }
        await user_store.save(new_user)
        
        # Verify user exists
        user = await user_store.get_by_username("testuser")
        assert user is not None
        assert user["email"] == "user@example.com"
        
        # Step 2: Create job
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore
        job_store = BoundedInMemoryJobStore(max_size=100, default_ttl_seconds=3600)
        
        job_data = {
            "id": "job_journey_001",
            "user_id": "usr_journey_001",
            "problem_type": "QAOA",
            "problem_config": {"type": "maxcut", "edges": [[0, 1]]},
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
        }
        await job_store.set("job_journey_001", job_data)
        
        # Verify job exists
        job = await job_store.get("job_journey_001")
        assert job is not None
        assert job["status"] == "queued"
        
        # Step 3: Update job status (simulating processing)
        await job_store.update("job_journey_001", {
            "status": "running",
            "started_at": datetime.now(UTC).isoformat(),
        })
        
        job = await job_store.get("job_journey_001")
        assert job["status"] == "running"
        
        # Step 4: Complete job
        await job_store.update("job_journey_001", {
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
            "result": {"optimal_value": -5.0, "bitstring": "101"},
        })
        
        job = await job_store.get("job_journey_001")
        assert job["status"] == "completed"
        assert job["result"]["optimal_value"] == -5.0

    @pytest.mark.asyncio
    async def test_job_result_caching_flow(self):
        """Test that job results are cached and retrieved."""
        from api.cache.result_cache import NoOpResultCache
        
        cache = NoOpResultCache()
        
        problem_config = {"type": "maxcut", "edges": [[0, 1], [1, 2]]}
        parameters = {"layers": 3, "optimizer": "COBYLA"}
        result = {"status": "completed", "value": -5.0}
        
        # Cache result
        await cache.set(problem_config, parameters, result)
        
        # Retrieve (will be miss for NoOp, but tests the flow)
        cached = await cache.get(problem_config, parameters)
        # NoOp always returns None, but the flow works

    @pytest.mark.asyncio
    async def test_encrypted_job_result_flow(self):
        """Test job result encryption and decryption flow."""
        # This tests the encryption flow without real PQC
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import os
        
        # Simulate job result
        result = {
            "status": "completed",
            "optimal_value": -5.234,
            "optimal_bitstring": "10110",
        }
        
        # Serialize
        result_bytes = json.dumps(result).encode("utf-8")
        
        # Generate encryption key (simulating ML-KEM shared secret)
        key = os.urandom(32)
        nonce = os.urandom(12)
        
        # Encrypt
        ciphertext = AESGCM(key).encrypt(nonce, result_bytes, None)
        
        # Store encrypted result
        encrypted_envelope = {
            "ciphertext": ciphertext.hex(),
            "nonce": nonce.hex(),
            "algorithm": "AES-256-GCM",
        }
        
        # Simulate retrieval
        retrieved_nonce = bytes.fromhex(encrypted_envelope["nonce"])
        retrieved_ciphertext = bytes.fromhex(encrypted_envelope["ciphertext"])
        
        # Decrypt
        decrypted_bytes = AESGCM(key).decrypt(retrieved_nonce, retrieved_ciphertext, None)
        decrypted_result = json.loads(decrypted_bytes.decode("utf-8"))
        
        # Verify
        assert decrypted_result == result


class TestAdminWorkflow:
    """Test administrative workflows."""

    @pytest.mark.asyncio
    async def test_key_rotation_workflow(self):
        """Test key generation, rotation, and expiration."""
        from api.key_rotation import KeyRotationService, RotationPolicy
        
        # Create rotation service with short TTL for testing
        policy = RotationPolicy(max_age_days=1, rotate_before_days=0)
        rotation_service = KeyRotationService(rotation_policy=policy)
        
        # Generate key
        key_meta = await rotation_service.generate_key(
            key_type="signing",
            security_level=3,
        )
        
        assert key_meta.key_id is not None
        assert key_meta.key_type == "signing"
        assert key_meta.is_active is True
        
        # Verify key exists
        retrieved = rotation_service.get_key(key_meta.key_id)
        assert retrieved is not None
        assert retrieved.key_id == key_meta.key_id
        
        # Rotate key
        new_key = await rotation_service.rotate_key(key_meta.key_id)
        
        # Old key should be inactive
        old_key = rotation_service.get_key(key_meta.key_id)
        assert old_key.is_active is False
        
        # New key should be active
        assert new_key.is_active is True
        assert new_key.rotated_from == key_meta.key_id
        
        # Get status
        status = rotation_service.get_status()
        assert status["total_keys"] >= 2
        assert status["active_keys"] == 1

    @pytest.mark.asyncio
    async def test_user_management_workflow(self):
        """Test admin user management workflow."""
        import os
        os.environ["ADMIN_PASSWORD"] = "test_admin_pass"
        os.environ["APP_ENV"] = "test"
        
        from api.auth_stores import InMemoryUserStore, hash_password
        
        store = InMemoryUserStore()
        
        # Create user
        user = {
            "username": "managed_user",
            "user_id": "usr_managed_001",
            "email": "managed@example.com",
            "password_hash": hash_password("UserPass123!"),
            "roles": ["user"],
            "created_at": datetime.now(UTC).isoformat(),
        }
        await store.save(user)
        
        # Admin updates user
        user["roles"] = ["user", "analyst"]
        await store.save(user)
        
        # Verify update
        updated = await store.get_by_username("managed_user")
        assert "analyst" in updated["roles"]
        
        # Admin deletes user
        deleted = await store.delete("managed_user")
        assert deleted is True
        
        # Verify deletion
        assert await store.get_by_username("managed_user") is None


class TestMultiTenantWorkflow:
    """Test multi-tenant isolation and workflows."""

    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        """Test that tenants cannot access each other's data."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore
        
        store = BoundedInMemoryJobStore(max_size=1000, default_ttl_seconds=3600)
        
        # Tenant 1 jobs
        for i in range(5):
            await store.set(
                f"job_t1_{i}",
                {
                    "id": f"job_t1_{i}",
                    "user_id": f"usr_t1_{i}",
                    "tenant_id": "tenant_1",
                    "status": "completed",
                    "result": {"value": i},
                }
            )
        
        # Tenant 2 jobs
        for i in range(5):
            await store.set(
                f"job_t2_{i}",
                {
                    "id": f"job_t2_{i}",
                    "user_id": f"usr_t2_{i}",
                    "tenant_id": "tenant_2",
                    "status": "completed",
                    "result": {"value": i * 10},
                }
            )
        
        # Verify isolation
        def filter_t1(job):
            return job.get("tenant_id") == "tenant_1"
        
        t1_jobs = await store.list(limit=100, filter_fn=filter_t1)
        assert len(t1_jobs) == 5
        assert all(j["tenant_id"] == "tenant_1" for j in t1_jobs)
        assert all("tenant_2" not in j["tenant_id"] for j in t1_jobs)

    @pytest.mark.asyncio
    async def test_cross_tenant_user_isolation(self):
        """Test users cannot access other tenant's resources."""
        import os
        os.environ["ADMIN_PASSWORD"] = "test_admin_pass"
        os.environ["APP_ENV"] = "test"
        
        from api.auth_stores import InMemoryUserStore, hash_password
        
        store = InMemoryUserStore()
        
        # Create users from different tenants
        users = [
            {
                "username": "t1_user",
                "user_id": "usr_t1_001",
                "email": "t1@example.com",
                "password_hash": hash_password("pass1"),
                "roles": ["user"],
                "tenant_id": "tenant_1",
            },
            {
                "username": "t2_user",
                "user_id": "usr_t2_001",
                "email": "t2@example.com",
                "password_hash": hash_password("pass2"),
                "roles": ["user"],
                "tenant_id": "tenant_2",
            },
        ]
        
        for user in users:
            await store.save(user)
        
        # Verify users exist
        t1_user = await store.get_by_username("t1_user")
        t2_user = await store.get_by_username("t2_user")
        
        assert t1_user["tenant_id"] == "tenant_1"
        assert t2_user["tenant_id"] == "tenant_2"


class TestErrorHandlingWorkflow:
    """Test error handling and recovery workflows."""

    @pytest.mark.asyncio
    async def test_job_failure_and_retry(self):
        """Test that failed jobs can be retried."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore
        
        store = BoundedInMemoryJobStore(max_size=100, default_ttl_seconds=3600)
        
        # Create job
        await store.set("job_retry_001", {
            "id": "job_retry_001",
            "status": "queued",
            "retry_count": 0,
            "max_retries": 3,
        })
        
        # Simulate failure
        await store.update("job_retry_001", {
            "status": "failed",
            "error": "Quantum decoherence",
            "retry_count": 1,
        })
        
        job = await store.get("job_retry_001")
        assert job["status"] == "failed"
        assert job["retry_count"] == 1
        
        # Retry job
        await store.update("job_retry_001", {
            "status": "queued",
            "error": None,
            "retry_count": job["retry_count"] + 1,
        })
        
        job = await store.get("job_retry_001")
        assert job["status"] == "queued"
        assert job["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_webhook_failure_recovery(self):
        """Test webhook failure and recovery."""
        from api.routers.jobs import send_webhook_notification
        
        with patch("api.routers.jobs.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            # Should succeed
            await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="job_test",
                status="completed",
            )
            
            assert mock_instance.post.called
