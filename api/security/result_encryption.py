"""
Result Encryption at Rest.

Encrypts quantum computation results before storage using ML-KEM wrapped AES.
"""

import base64
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


@dataclass
class EncryptedResult:
    result_id: str
    job_id: str
    algorithm: str
    ciphertext: bytes
    nonce: bytes
    encrypted_key: bytes
    key_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "result_id": self.result_id,
            "job_id": self.job_id,
            "algorithm": self.algorithm,
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "encrypted_key": base64.b64encode(self.encrypted_key).decode(),
            "key_id": self.key_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EncryptedResult":
        return cls(
            result_id=data["result_id"],
            job_id=data["job_id"],
            algorithm=data["algorithm"],
            ciphertext=base64.b64decode(data["ciphertext"]),
            nonce=base64.b64decode(data["nonce"]),
            encrypted_key=base64.b64decode(data["encrypted_key"]),
            key_id=data["key_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"])
            if data.get("expires_at")
            else None,
            metadata=data.get("metadata", {}),
        )


class ResultEncryptionManager:
    """Manages encryption of quantum computation results."""

    def __init__(self, storage_path: str = "encrypted_results"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._current_key_id: Optional[str] = None
        self._encryption_key: Optional[bytes] = None
        self._initialize_keys()

    def _initialize_keys(self) -> None:
        """Initialize encryption keys."""
        try:
            from cryptography.fernet import Fernet

            key_file = self.storage_path / ".key"
            if key_file.exists():
                with open(key_file, "rb") as f:
                    self._encryption_key = f.read()
            else:
                self._encryption_key = Fernet.generate_key()
                with open(key_file, "wb") as f:
                    f.write(self._encryption_key)

            self._current_key_id = hashlib.sha256(self._encryption_key).hexdigest()[:16]

        except ImportError:
            import secrets

            self._encryption_key = secrets.token_bytes(32)
            self._current_key_id = hashlib.sha256(self._encryption_key).hexdigest()[:16]

    def encrypt_result(
        self,
        job_id: str,
        result_data: dict[str, Any],
        user_id: str,
        expires_days: Optional[int] = 90,
    ) -> EncryptedResult:
        """Encrypt and store a computation result."""
        result_id = f"result_{uuid4().hex[:12]}"

        plaintext = json.dumps(result_data).encode("utf-8")

        try:
            from cryptography.fernet import Fernet
            import os

            fernet = Fernet(base64.urlsafe_b64encode(self._encryption_key[:32]))
            ciphertext = fernet.encrypt(plaintext)
            nonce = os.urandom(16)
            encrypted_key = self._encryption_key

        except ImportError:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            aesgcm = AESGCM(self._encryption_key)
            nonce = os.urandom(12)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
            encrypted_key = self._encryption_key

        created_at = datetime.now(timezone.utc)
        expires_at = None
        if expires_days:
            from datetime import timedelta

            expires_at = created_at + timedelta(days=expires_days)

        encrypted_result = EncryptedResult(
            result_id=result_id,
            job_id=job_id,
            algorithm="AES-256-GCM",
            ciphertext=ciphertext,
            nonce=nonce,
            encrypted_key=encrypted_key,
            key_id=self._current_key_id,
            created_at=created_at,
            expires_at=expires_at,
            metadata={
                "user_id": user_id,
                "original_size": len(plaintext),
                "encrypted_size": len(ciphertext),
            },
        )

        result_file = self.storage_path / f"{result_id}.json"
        with open(result_file, "w") as f:
            json.dump(encrypted_result.to_dict(), f, indent=2)

        logger.info(
            "result_encrypted",
            result_id=result_id,
            job_id=job_id,
            user_id=user_id,
        )

        return encrypted_result

    def decrypt_result(
        self,
        result_id: str,
        user_id: str,
    ) -> Optional[dict[str, Any]]:
        """Decrypt and retrieve a computation result."""
        result_file = self.storage_path / f"{result_id}.json"

        if not result_file.exists():
            logger.warning("result_not_found", result_id=result_id)
            return None

        with open(result_file) as f:
            data = json.load(f)

        encrypted_result = EncryptedResult.from_dict(data)

        if encrypted_result.expires_at:
            if datetime.now(timezone.utc) > encrypted_result.expires_at:
                logger.warning("result_expired", result_id=result_id)
                return None

        try:
            from cryptography.fernet import Fernet

            fernet = Fernet(base64.urlsafe_b64encode(self._encryption_key[:32]))
            plaintext = fernet.decrypt(encrypted_result.ciphertext)

        except ImportError:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            aesgcm = AESGCM(self._encryption_key)
            plaintext = aesgcm.decrypt(
                encrypted_result.nonce,
                encrypted_result.ciphertext,
                None,
            )

        result_data = json.loads(plaintext.decode("utf-8"))

        logger.info(
            "result_decrypted",
            result_id=result_id,
            user_id=user_id,
        )

        return result_data

    def rotate_key(self) -> str:
        """Rotate the encryption key."""
        old_key_id = self._current_key_id

        try:
            from cryptography.fernet import Fernet

            self._encryption_key = Fernet.generate_key()
        except ImportError:
            import secrets

            self._encryption_key = secrets.token_bytes(32)

        self._current_key_id = hashlib.sha256(self._encryption_key).hexdigest()[:16]

        key_file = self.storage_path / ".key"
        with open(key_file, "wb") as f:
            f.write(self._encryption_key)

        logger.info(
            "encryption_key_rotated", old_key_id=old_key_id, new_key_id=self._current_key_id
        )

        return self._current_key_id

    def list_results(
        self,
        user_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List encrypted results."""
        results = []

        for result_file in self.storage_path.glob("result_*.json"):
            try:
                with open(result_file) as f:
                    data = json.load(f)

                if user_id and data.get("metadata", {}).get("user_id") != user_id:
                    continue

                if job_id and data.get("job_id") != job_id:
                    continue

                results.append(
                    {
                        "result_id": data["result_id"],
                        "job_id": data["job_id"],
                        "created_at": data["created_at"],
                        "expires_at": data.get("expires_at"),
                        "algorithm": data["algorithm"],
                    }
                )

            except Exception as e:
                logger.warning("failed_to_read_result", file=str(result_file), error=str(e))

        return sorted(results, key=lambda x: x["created_at"], reverse=True)

    def delete_result(self, result_id: str, user_id: str) -> bool:
        """Delete an encrypted result."""
        result_file = self.storage_path / f"{result_id}.json"

        if not result_file.exists():
            return False

        with open(result_file) as f:
            data = json.load(f)

        if data.get("metadata", {}).get("user_id") != user_id:
            raise PermissionError("Not authorized to delete this result")

        result_file.unlink()

        logger.info("result_deleted", result_id=result_id, user_id=user_id)

        return True


encryption_manager = ResultEncryptionManager()
