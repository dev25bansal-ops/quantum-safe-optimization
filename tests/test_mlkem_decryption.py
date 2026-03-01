"""
Test ML-KEM decryption endpoint for job results.
"""

import json
import time

import requests
from quantum_safe_crypto import py_kem_generate_with_level

BASE_URL = "http://localhost:8000/api/v1"


def test_mlkem_decryption():
    """Test decrypting encrypted job results."""

    # Generate a local key pair for testing
    keypair = py_kem_generate_with_level(3)  # Level 3 = ML-KEM-768
    public_key = keypair.public_key
    secret_key = keypair.secret_key

    # Register user
    username = f"decrypt_test_{int(time.time())}"
    reg_resp = requests.post(
        f"{BASE_URL}/auth/register", json={"username": username, "password": "TestPassword123!"}
    )
    assert reg_resp.status_code in [201, 200]

    # Login
    login_resp = requests.post(
        f"{BASE_URL}/auth/login", json={"username": username, "password": "TestPassword123!"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Register our local public key
    reg_key_resp = requests.put(
        f"{BASE_URL}/auth/keys/encryption-key",
        headers=headers,
        json={"public_key": public_key, "key_type": "ML-KEM-768"},
    )
    assert reg_key_resp.status_code == 200

    # Submit encrypted job
    job_resp = requests.post(
        f"{BASE_URL}/jobs",
        headers=headers,
        json={
            "problem_type": "QAOA",
            "problem_config": {
                "problem": "maxcut",
                "edges": [[0, 1], [1, 2], [2, 0]],
            },
            "parameters": {"layers": 1, "shots": 50},
            "encrypt_result": True,
        },
    )
    job_id = job_resp.json()["job_id"]

    # Wait for completion
    for _ in range(20):
        status_resp = requests.get(f"{BASE_URL}/jobs/{job_id}", headers=headers)
        if status_resp.json()["status"] == "completed":
            break
        time.sleep(0.5)

    # Get encrypted result
    result_resp = requests.get(f"{BASE_URL}/jobs/{job_id}/result", headers=headers)
    result_data = result_resp.json()

    assert result_data["encrypted"], "Result should be encrypted"
    encrypted_envelope = result_data["encrypted_result"]

    # Decrypt using server endpoint
    decrypt_resp = requests.post(
        f"{BASE_URL}/jobs/{job_id}/decrypt", headers=headers, json={"secret_key": secret_key}
    )

    assert decrypt_resp.status_code == 200, f"Decryption failed: {decrypt_resp.text}"
    decrypted_data = decrypt_resp.json()

    assert decrypted_data["decrypted"], "Result should be marked as decrypted"
    result = decrypted_data["result"]

    # Also test client-side decryption
    from quantum_safe_crypto import EncryptedEnvelope, py_decrypt

    envelope = EncryptedEnvelope.from_json(encrypted_envelope)
    decrypted_bytes = py_decrypt(envelope, secret_key)
    client_result = json.loads(decrypted_bytes.decode("utf-8"))

    assert client_result["optimal_value"] == result["optimal_value"]

    return True


if __name__ == "__main__":
    try:
        success = test_mlkem_decryption()
        exit(0 if success else 1)
    except Exception:
        import traceback

        traceback.print_exc()
        exit(1)
