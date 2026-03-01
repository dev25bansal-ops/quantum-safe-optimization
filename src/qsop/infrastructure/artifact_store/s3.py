"""
S3 artifact store for production.

Stores encrypted artifacts in AWS S3 or compatible storage.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ArtifactMetadata:
    """Metadata for stored artifacts."""

    artifact_id: str
    content_type: str
    size: int
    hash: str
    created_at: datetime
    metadata: dict


logger = logging.getLogger(__name__)


@dataclass
class S3ArtifactStore:
    """
    S3-based artifact store.

    Stores artifacts in S3 with metadata in object tags/headers.
    """

    bucket: str = "qsop-artifacts"
    prefix: str = "artifacts/"
    region: str = "us-east-1"
    endpoint_url: str | None = None  # For S3-compatible stores
    _client: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize S3 client."""
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Set up the S3 client."""
        try:
            import boto3

            kwargs = {"region_name": self.region}
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url

            self._client = boto3.client("s3", **kwargs)

        except ImportError:
            logger.warning("boto3 not installed. Install with: pip install boto3")
            self._client = None

    def _object_key(self, artifact_id: str) -> str:
        """Get S3 object key for an artifact."""
        return f"{self.prefix}{artifact_id}"

    def store(
        self,
        artifact_id: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> ArtifactMetadata:
        """Store an artifact in S3."""
        if self._client is None:
            raise RuntimeError("S3 client not initialized")

        # Compute hash
        data_hash = hashlib.sha256(data).hexdigest()
        created_at = datetime.now(UTC)

        # Prepare S3 metadata (must be string values)
        s3_metadata = {
            "artifact-id": artifact_id,
            "content-hash": data_hash,
            "created-at": created_at.isoformat(),
        }

        if metadata:
            s3_metadata["custom-metadata"] = json.dumps(metadata)

        # Upload to S3
        self._client.put_object(
            Bucket=self.bucket,
            Key=self._object_key(artifact_id),
            Body=data,
            ContentType=content_type,
            Metadata=s3_metadata,
            ChecksumAlgorithm="SHA256",
        )

        return ArtifactMetadata(
            artifact_id=artifact_id,
            content_type=content_type,
            size=len(data),
            hash=data_hash,
            created_at=created_at,
            metadata=metadata or {},
        )

    def retrieve(self, artifact_id: str) -> tuple[bytes, ArtifactMetadata]:
        """Retrieve an artifact from S3."""
        if self._client is None:
            raise RuntimeError("S3 client not initialized")

        try:
            response = self._client.get_object(
                Bucket=self.bucket,
                Key=self._object_key(artifact_id),
            )

            data = response["Body"].read()
            s3_metadata = response.get("Metadata", {})

            # Parse metadata
            custom_metadata = {}
            if "custom-metadata" in s3_metadata:
                custom_metadata = json.loads(s3_metadata["custom-metadata"])

            metadata = ArtifactMetadata(
                artifact_id=artifact_id,
                content_type=response.get("ContentType", "application/octet-stream"),
                size=len(data),
                hash=s3_metadata.get("content-hash", ""),
                created_at=datetime.fromisoformat(
                    s3_metadata.get("created-at", datetime.now(UTC).isoformat())
                ),
                metadata=custom_metadata,
            )

            # Verify hash
            actual_hash = hashlib.sha256(data).hexdigest()
            if metadata.hash and actual_hash != metadata.hash:
                raise ValueError(f"Artifact integrity check failed: {artifact_id}")

            return data, metadata

        except self._client.exceptions.NoSuchKey as e:
            raise KeyError(f"Artifact not found: {artifact_id}") from e

    def delete(self, artifact_id: str) -> None:
        """Delete an artifact from S3."""
        if self._client is None:
            raise RuntimeError("S3 client not initialized")

        self._client.delete_object(
            Bucket=self.bucket,
            Key=self._object_key(artifact_id),
        )

    def exists(self, artifact_id: str) -> bool:
        """Check if artifact exists in S3."""
        if self._client is None:
            raise RuntimeError("S3 client not initialized")

        try:
            self._client.head_object(
                Bucket=self.bucket,
                Key=self._object_key(artifact_id),
            )
            return True
        except Exception:
            return False

    def get_metadata(self, artifact_id: str) -> ArtifactMetadata:
        """Get artifact metadata without retrieving data."""
        if self._client is None:
            raise RuntimeError("S3 client not initialized")

        try:
            response = self._client.head_object(
                Bucket=self.bucket,
                Key=self._object_key(artifact_id),
            )

            s3_metadata = response.get("Metadata", {})

            custom_metadata = {}
            if "custom-metadata" in s3_metadata:
                custom_metadata = json.loads(s3_metadata["custom-metadata"])

            return ArtifactMetadata(
                artifact_id=artifact_id,
                content_type=response.get("ContentType", "application/octet-stream"),
                size=response.get("ContentLength", 0),
                hash=s3_metadata.get("content-hash", ""),
                created_at=datetime.fromisoformat(
                    s3_metadata.get("created-at", datetime.now(UTC).isoformat())
                ),
                metadata=custom_metadata,
            )

        except Exception as e:
            raise KeyError(f"Artifact not found: {artifact_id}") from e

    def list_artifacts(
        self,
        prefix: str | None = None,
        limit: int = 100,
    ) -> list[ArtifactMetadata]:
        """List artifacts in S3."""
        if self._client is None:
            raise RuntimeError("S3 client not initialized")

        search_prefix = self.prefix
        if prefix:
            search_prefix = f"{self.prefix}{prefix}"

        result = []

        paginator = self._client.get_paginator("list_objects_v2")

        for page in paginator.paginate(
            Bucket=self.bucket,
            Prefix=search_prefix,
            MaxKeys=limit,
        ):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                artifact_id = key[len(self.prefix) :]

                try:
                    metadata = self.get_metadata(artifact_id)
                    result.append(metadata)
                except Exception:
                    continue

                if len(result) >= limit:
                    return result

        return result

    def generate_presigned_url(
        self,
        artifact_id: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """Generate a presigned URL for direct access."""
        if self._client is None:
            raise RuntimeError("S3 client not initialized")

        return self._client.generate_presigned_url(
            method,
            Params={
                "Bucket": self.bucket,
                "Key": self._object_key(artifact_id),
            },
            ExpiresIn=expires_in,
        )
