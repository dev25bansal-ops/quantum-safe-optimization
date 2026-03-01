"""
Test ML-KEM encryption integration with job results.
"""

import time

import requests

BASE_URL = "http://localhost:8000"


def test_mlkem_job_encryption():
    """Test full ML-KEM encryption flow for job results."""

    # 1. Register a new user
    reg_resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={"username": f"mlkem_test_{int(time.time())}", "password": "TestPassword123!"},
    )
    assert reg_resp.status_code in [201, 200], f"Registration failed: {reg_resp.text}"
    user_data = reg_resp.json()
    username = user_data.get("username")

    # 2. Login
    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": username, "password": "TestPassword123!"},
        timeout=5,
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 3. Generate ML-KEM key pair
    key_resp = requests.post(
        f"{BASE_URL}/auth/keys/generate", headers=headers, json={"key_type": "kem"}
    )
    assert key_resp.status_code == 200, f"Key generation failed: {key_resp.text}"
    key_data = key_resp.json()
    public_key = key_data["public_key"]
    key_data["key_id"]

    # 4. Register public key for result encryption
    reg_key_resp = requests.put(
        f"{BASE_URL}/auth/keys/encryption-key",
        timeout=5,
        headers=headers,
        json={"public_key": public_key, "key_type": "ML-KEM-768"},
    )
    assert reg_key_resp.status_code == 200, f"Key registration failed: {reg_key_resp.text}"

    # 5. Submit job with encryption enabled
    job_resp = requests.post(
        f"{BASE_URL}/jobs",
        headers=headers,
        json={
            "problem_type": "QAOA",
            "problem_config": {
                "problem": "maxcut",
                "edges": [[0, 1], [1, 2], [2, 0], [0, 3], [3, 2]],
            },
            "parameters": {"layers": 2, "shots": 100},
            "encrypt_result": True,
        },
    )
    assert job_resp.status_code == 202, f"Job submission failed: {job_resp.text}"
    job_data = job_resp.json()
    job_id = job_data["job_id"]

    # 6. Wait for job completion
    max_wait = 30
    for _i in range(max_wait):
        status_resp = requests.get(f"{BASE_URL}/jobs/{job_id}", headers=headers, timeout=5)
        status = status_resp.json()["status"]
        if status == "completed":
            break
        if status == "failed":
            return False
        time.sleep(1)

    if status != "completed":
        return False

    # 7. Get encrypted result
    result_resp = requests.get(f"{BASE_URL}/jobs/{job_id}/result", headers=headers, timeout=5)
    assert result_resp.status_code == 200, f"Failed to get result: {result_resp.text}"
    result_data = result_resp.json()

    result_data.get("encrypted", False)
    encrypted_result = result_data.get("encrypted_result")

    if encrypted_result:
        pass
    else:
        pass

    # 8. Verify encryption info endpoint
    info_resp = requests.get(f"{BASE_URL}/jobs/encryption/info", timeout=5)
    assert info_resp.status_code == 200
    info_resp.json()

    return True


if __name__ == "__main__":
    try:
        success = test_mlkem_job_encryption()
        exit(0 if success else 1)
    except Exception:
        import traceback

        traceback.print_exc()
        exit(1)
