#!/usr/bin/env python3
"""
Client-Side Decryption Library

This module provides client-side decryption functionality for encrypted job results.
Your secret key never leaves your device, ensuring maximum security.

Usage:
    python3 decrypt_client.py <encrypted_result_json> <your_ml_kem_secret_key_base64>
"""

import argparse
import sys
import json

try:
    from quantum_safe_crypto import EncryptedEnvelope, py_decrypt
except ImportError:
    print("Error: quantum_safe_crypto module not found")
    print("Install: pip install -e .")
    sys.exit(1)


def decrypt_result_client_side(encrypted_json: str, secret_key: str) -> dict:
    """
    Decrypt an encrypted job result using your ML-KEM secret key.

    This operation is performed entirely on your machine - the secret key
    is never transmitted to any server.

    Args:
        encrypted_json: JSON-serialized encrypted envelope (from API /jobs/{id}/result)
        secret_key: Your ML-KEM-768 secret key (base64 encoded)

    Returns:
        Dictionary containing the decrypted job result

    Raises:
        ValueError: If decryption fails
    """
    try:
        # Parse the encrypted envelope from JSON
        envelope = EncryptedEnvelope.from_json(encrypted_json)

        # Decrypt using ML-KEM-768 + AES-256-GCM
        decrypted_bytes = py_decrypt(envelope, secret_key)

        # Parse the JSON result
        result = json.loads(decrypted_bytes.decode("utf-8"))

        return result

    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")


def decrypt_from_api(job_id: str, secret_key: str, api_base: str = "http://localhost:8000") -> dict:
    """
    Fetch and decrypt a job result from the API.

    This combines fetching the encrypted result from the API with
    local client-side decryption.

    Args:
        job_id: The job identifier
        secret_key: Your ML-KEM-768 secret key (base64 encoded)
        api_base: Base URL of the API (default: http://localhost:8000)

    Returns:
        Dictionary containing the decrypted job result
    """
    import requests

    # Fetch the encrypted result from the API
    response = requests.get(f"{api_base}/api/jobs/{job_id}/result")
    response.raise_for_status()

    data = response.json()

    if not data.get("encrypted"):
        # Result wasn't encrypted, return plaintext
        return data.get("result")

    encrypted_result = data.get("encrypted_result")
    if not encrypted_result:
        raise ValueError("No encrypted result found")

    # Decrypt locally
    return decrypt_result_client_side(encrypted_result, secret_key)


def main():
    parser = argparse.ArgumentParser(description="Decrypt QRSEF job results client-side (secure)")
    parser.add_argument(
        "input",
        help="Either: (1) job_id to fetch from API, or (2) path to encrypted_result.json file, or (3) encrypted JSON string",
    )
    parser.add_argument("secret_key", help="Your ML-KEM-768 secret key (base64 encoded)")
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--format", choices=["json", "pretty"], default="pretty", help="Output format"
    )

    args = parser.parse_args()

    # Determine input type
    if args.input.startswith("job_"):
        # It's a job ID - fetch from API
        try:
            result = decrypt_from_api(args.input, args.secret_key, args.api_base)
        except Exception as e:
            print(f"Error fetching/decrypting from API: {e}")
            sys.exit(1)
    elif args.input.startswith("{"):
        # It's JSON string
        try:
            result = decrypt_result_client_side(args.input, args.secret_key)
        except Exception as e:
            print(f"Error decrypting JSON string: {e}")
            sys.exit(1)
    else:
        # Assume it's a file path
        try:
            with open(args.input, "r") as f:
                encrypted_json = f.read()
            result = decrypt_result_client_side(encrypted_json, args.secret_key)
        except FileNotFoundError:
            print(f"Error: File not found: {args.input}")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading/decrypting file: {e}")
            sys.exit(1)

    # Output result
    if args.format == "pretty":
        print(json.dumps(result, indent=2, default=str))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
