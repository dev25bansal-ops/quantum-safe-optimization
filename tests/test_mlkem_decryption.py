"""
Test ML-KEM decryption endpoint for job results.
"""

import requests
import time
import json
from quantum_safe_crypto import py_kem_generate_with_level


BASE_URL = "http://localhost:8000/api/v1"


def test_mlkem_decryption():
    """Test decrypting encrypted job results."""
    
    # Generate a local key pair for testing
    print("\n1. Generating local ML-KEM-768 key pair...")
    keypair = py_kem_generate_with_level(3)  # Level 3 = ML-KEM-768
    public_key = keypair.public_key
    secret_key = keypair.secret_key
    print(f"   ✓ Public key: {len(public_key)} chars")
    print(f"   ✓ Secret key: {len(secret_key)} chars")
    
    # Register user
    username = f"decrypt_test_{int(time.time())}"
    print(f"\n2. Registering user {username}...")
    reg_resp = requests.post(f"{BASE_URL}/auth/register", json={
        "username": username,
        "password": "TestPassword123!"
    })
    assert reg_resp.status_code in [201, 200]
    print(f"   ✓ User registered")
    
    # Login
    print("\n3. Logging in...")
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": "TestPassword123!"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"   ✓ Got token")
    
    # Register our local public key
    print("\n4. Registering local public key for encryption...")
    reg_key_resp = requests.put(f"{BASE_URL}/auth/keys/encryption-key",
        headers=headers, json={"public_key": public_key, "key_type": "ML-KEM-768"})
    assert reg_key_resp.status_code == 200
    print(f"   ✓ Key registered")
    
    # Submit encrypted job
    print("\n5. Submitting encrypted job...")
    job_resp = requests.post(f"{BASE_URL}/jobs", headers=headers, json={
        "problem_type": "QAOA",
        "problem_config": {
            "problem": "maxcut",
            "edges": [[0, 1], [1, 2], [2, 0]],
        },
        "parameters": {"layers": 1, "shots": 50},
        "encrypt_result": True
    })
    job_id = job_resp.json()["job_id"]
    print(f"   ✓ Job: {job_id}")
    
    # Wait for completion
    print("\n6. Waiting for completion...")
    for _ in range(20):
        status_resp = requests.get(f"{BASE_URL}/jobs/{job_id}", headers=headers)
        if status_resp.json()["status"] == "completed":
            break
        time.sleep(0.5)
    print(f"   ✓ Job completed")
    
    # Get encrypted result
    print("\n7. Getting encrypted result...")
    result_resp = requests.get(f"{BASE_URL}/jobs/{job_id}/result", headers=headers)
    result_data = result_resp.json()
    
    assert result_data["encrypted"], "Result should be encrypted"
    encrypted_envelope = result_data["encrypted_result"]
    print(f"   ✓ Got encrypted envelope")
    
    # Decrypt using server endpoint
    print("\n8. Decrypting via server endpoint...")
    decrypt_resp = requests.post(f"{BASE_URL}/jobs/{job_id}/decrypt",
        headers=headers, json={"secret_key": secret_key})
    
    assert decrypt_resp.status_code == 200, f"Decryption failed: {decrypt_resp.text}"
    decrypted_data = decrypt_resp.json()
    
    assert decrypted_data["decrypted"], "Result should be marked as decrypted"
    result = decrypted_data["result"]
    
    print(f"   ✓ Decryption successful!")
    print(f"   ✓ Optimal value: {result.get('optimal_value')}")
    print(f"   ✓ Optimal bitstring: {result.get('optimal_bitstring')}")
    
    # Also test client-side decryption
    print("\n9. Testing client-side decryption...")
    from quantum_safe_crypto import py_decrypt, EncryptedEnvelope
    
    envelope = EncryptedEnvelope.from_json(encrypted_envelope)
    decrypted_bytes = py_decrypt(envelope, secret_key)
    client_result = json.loads(decrypted_bytes.decode('utf-8'))
    
    assert client_result["optimal_value"] == result["optimal_value"]
    print(f"   ✓ Client-side decryption matches server result!")
    
    print("\n" + "="*50)
    print("✓ ML-KEM DECRYPTION TEST PASSED!")
    print("="*50)
    return True


if __name__ == "__main__":
    try:
        success = test_mlkem_decryption()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
