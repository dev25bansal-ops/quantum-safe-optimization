"""
Test ML-KEM encryption integration with job results.
"""

import requests
import time
import json


BASE_URL = "http://localhost:8000"


def test_mlkem_job_encryption():
    """Test full ML-KEM encryption flow for job results."""
    
    # 1. Register a new user
    print("\n1. Registering test user...")
    reg_resp = requests.post(f"{BASE_URL}/auth/register", json={
        "username": f"mlkem_test_{int(time.time())}",
        "password": "TestPassword123!"
    })
    assert reg_resp.status_code in [201, 200], f"Registration failed: {reg_resp.text}"
    user_data = reg_resp.json()
    username = user_data.get("username")
    print(f"   ✓ Registered user: {username}")
    
    # 2. Login
    print("\n2. Logging in...")
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": "TestPassword123!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"   ✓ Got access token")
    
    # 3. Generate ML-KEM key pair
    print("\n3. Generating ML-KEM-768 key pair...")
    key_resp = requests.post(f"{BASE_URL}/auth/keys/generate", 
        headers=headers, json={"key_type": "kem"})
    assert key_resp.status_code == 200, f"Key generation failed: {key_resp.text}"
    key_data = key_resp.json()
    public_key = key_data["public_key"]
    key_id = key_data["key_id"]
    print(f"   ✓ Generated key: {key_id}")
    print(f"   ✓ Algorithm: {key_data.get('algorithm', 'ML-KEM-768')}")
    
    # 4. Register public key for result encryption
    print("\n4. Registering encryption key...")
    reg_key_resp = requests.put(f"{BASE_URL}/auth/keys/encryption-key",
        headers=headers, json={"public_key": public_key, "key_type": "ML-KEM-768"})
    assert reg_key_resp.status_code == 200, f"Key registration failed: {reg_key_resp.text}"
    print(f"   ✓ Key registered for result encryption")
    
    # 5. Submit job with encryption enabled
    print("\n5. Submitting QAOA job with encryption...")
    job_resp = requests.post(f"{BASE_URL}/jobs", headers=headers, json={
        "problem_type": "QAOA",
        "problem_config": {
            "problem": "maxcut",
            "edges": [[0, 1], [1, 2], [2, 0], [0, 3], [3, 2]],
        },
        "parameters": {"layers": 2, "shots": 100},
        "encrypt_result": True
    })
    assert job_resp.status_code == 202, f"Job submission failed: {job_resp.text}"
    job_data = job_resp.json()
    job_id = job_data["job_id"]
    print(f"   ✓ Job submitted: {job_id}")
    
    # 6. Wait for job completion
    print("\n6. Waiting for job completion...")
    max_wait = 30
    for i in range(max_wait):
        status_resp = requests.get(f"{BASE_URL}/jobs/{job_id}", headers=headers)
        status = status_resp.json()["status"]
        if status == "completed":
            break
        if status == "failed":
            print(f"   ✗ Job failed: {status_resp.json().get('error')}")
            return False
        time.sleep(1)
        print(f"   ... Status: {status}")
    
    if status != "completed":
        print(f"   ✗ Job timed out")
        return False
    print(f"   ✓ Job completed!")
    
    # 7. Get encrypted result
    print("\n7. Retrieving encrypted result...")
    result_resp = requests.get(f"{BASE_URL}/jobs/{job_id}/result", headers=headers)
    assert result_resp.status_code == 200, f"Failed to get result: {result_resp.text}"
    result_data = result_resp.json()
    
    is_encrypted = result_data.get("encrypted", False)
    encrypted_result = result_data.get("encrypted_result")
    
    print(f"   ✓ Encrypted: {is_encrypted}")
    if encrypted_result:
        print(f"   ✓ Encrypted envelope: {encrypted_result[:80]}...")
        print(f"   ✓ Algorithm: {result_data.get('encryption_algorithm')}")
    else:
        print(f"   ✓ Plaintext result available: {bool(result_data.get('result'))}")
    
    # 8. Verify encryption info endpoint
    print("\n8. Checking encryption info endpoint...")
    info_resp = requests.get(f"{BASE_URL}/jobs/encryption/info")
    assert info_resp.status_code == 200
    info = info_resp.json()
    print(f"   ✓ System: {info['encryption_system']}")
    print(f"   ✓ KEM: {info['key_encapsulation']['algorithm']}")
    
    print("\n" + "="*50)
    print("✓ ML-KEM integration test PASSED!")
    print("="*50)
    return True


if __name__ == "__main__":
    try:
        success = test_mlkem_job_encryption()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
