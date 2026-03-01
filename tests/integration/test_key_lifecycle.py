"""
Integration tests for key lifecycle management.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from qsop.application.services.key_lifecycle import KeyLifecycleManager
from qsop.crypto.pqc.algorithms import KEMAlgorithm
from qsop.domain.ports.keystore import KeyStatus, KeyType
from qsop.infrastructure.keystore.local_dev import LocalDevKeyStore


@pytest.mark.anyio
async def test_automated_key_rotation(tmp_path: Path):
    """Test that keys nearing expiration are automatically rotated."""
    # Setup
    keystore = LocalDevKeyStore(storage_path=tmp_path)

    # Create a key that is already "expired" (created 40 days ago with 30 day interval)
    old_created_at = datetime.now(UTC) - timedelta(days=40)

    # We need to manually inject a key with an old creation date
    # because store_key sets it to now()
    key_id = keystore.store_key(
        key_type=KeyType.KEM,
        algorithm=KEMAlgorithm.KYBER768.value,
        public_key=b"old_pub",
        secret_key=b"old_sec",
        key_id="test-key-1",
    )

    # Hack to update creation date for testing
    keystore._keys[key_id]["created_at"] = old_created_at.isoformat()
    keystore._save_metadata()

    # Verify setup
    meta = keystore.get_metadata(key_id)
    assert meta.created_at == old_created_at

    # Initialize lifecycle manager with short check interval
    manager = KeyLifecycleManager(
        keystore=keystore,
        check_interval_seconds=1,
        rotation_interval_days=30,
        warning_period_days=7,
    )

    # Start manager
    await manager.start()

    # Wait for rotation to happen
    await asyncio.sleep(2)

    # Stop manager
    await manager.stop()

    # Verify rotation
    old_meta = keystore.get_metadata(key_id)
    assert old_meta.status == KeyStatus.INACTIVE
    assert old_meta.rotated_to is not None

    new_id = old_meta.rotated_to
    new_meta = keystore.get_metadata(new_id)
    assert new_meta.status == KeyStatus.ACTIVE
    assert new_meta.rotated_from == key_id
    assert new_meta.algorithm == KEMAlgorithm.KYBER768.value

    # Verify new key is actually usable (has real keys, not our test strings)
    # The rotation service uses real keygen
    assert len(keystore.get_public_key(new_id)) > 10
    assert len(keystore.get_secret_key(new_id)) > 10
