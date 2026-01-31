"""
Filesystem artifact store for development.

Stores encrypted artifacts on the local filesystem.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ArtifactMetadata:
    """Metadata for stored artifacts."""
    artifact_id: str
    content_type: str
    size: int
    hash: str
    created_at: datetime
    metadata: dict


@dataclass
class FilesystemArtifactStore:
    """
    Local filesystem artifact store.
    
    Stores artifacts as files with metadata sidecars.
    """
    
    storage_path: Path = field(default_factory=lambda: Path.home() / ".qsop" / "artifacts")
    
    def __post_init__(self) -> None:
        """Initialize storage directory."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def store(
        self,
        artifact_id: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> ArtifactMetadata:
        """Store an artifact."""
        # Compute hash
        data_hash = hashlib.sha256(data).hexdigest()
        
        # Create metadata
        artifact_metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            content_type=content_type,
            size=len(data),
            hash=data_hash,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        
        # Store data file
        data_file = self.storage_path / f"{artifact_id}.bin"
        with open(data_file, "wb") as f:
            f.write(data)
        
        # Store metadata file
        meta_file = self.storage_path / f"{artifact_id}.meta.json"
        with open(meta_file, "w") as f:
            json.dump({
                "artifact_id": artifact_metadata.artifact_id,
                "content_type": artifact_metadata.content_type,
                "size": artifact_metadata.size,
                "hash": artifact_metadata.hash,
                "created_at": artifact_metadata.created_at.isoformat(),
                "metadata": artifact_metadata.metadata,
            }, f, indent=2)
        
        return artifact_metadata
    
    def retrieve(self, artifact_id: str) -> tuple[bytes, ArtifactMetadata]:
        """Retrieve an artifact."""
        data_file = self.storage_path / f"{artifact_id}.bin"
        meta_file = self.storage_path / f"{artifact_id}.meta.json"
        
        if not data_file.exists():
            raise KeyError(f"Artifact not found: {artifact_id}")
        
        # Read data
        with open(data_file, "rb") as f:
            data = f.read()
        
        # Read metadata
        with open(meta_file, "r") as f:
            meta_dict = json.load(f)
        
        metadata = ArtifactMetadata(
            artifact_id=meta_dict["artifact_id"],
            content_type=meta_dict["content_type"],
            size=meta_dict["size"],
            hash=meta_dict["hash"],
            created_at=datetime.fromisoformat(meta_dict["created_at"]),
            metadata=meta_dict.get("metadata", {}),
        )
        
        # Verify hash
        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != metadata.hash:
            raise ValueError(f"Artifact integrity check failed: {artifact_id}")
        
        return data, metadata
    
    def delete(self, artifact_id: str) -> None:
        """Delete an artifact."""
        data_file = self.storage_path / f"{artifact_id}.bin"
        meta_file = self.storage_path / f"{artifact_id}.meta.json"
        
        if data_file.exists():
            # Secure delete: overwrite with zeros
            size = data_file.stat().st_size
            with open(data_file, "wb") as f:
                f.write(b"\x00" * size)
            data_file.unlink()
        
        if meta_file.exists():
            meta_file.unlink()
    
    def exists(self, artifact_id: str) -> bool:
        """Check if artifact exists."""
        data_file = self.storage_path / f"{artifact_id}.bin"
        return data_file.exists()
    
    def get_metadata(self, artifact_id: str) -> ArtifactMetadata:
        """Get artifact metadata without retrieving data."""
        meta_file = self.storage_path / f"{artifact_id}.meta.json"
        
        if not meta_file.exists():
            raise KeyError(f"Artifact not found: {artifact_id}")
        
        with open(meta_file, "r") as f:
            meta_dict = json.load(f)
        
        return ArtifactMetadata(
            artifact_id=meta_dict["artifact_id"],
            content_type=meta_dict["content_type"],
            size=meta_dict["size"],
            hash=meta_dict["hash"],
            created_at=datetime.fromisoformat(meta_dict["created_at"]),
            metadata=meta_dict.get("metadata", {}),
        )
    
    def list_artifacts(
        self,
        prefix: str | None = None,
        limit: int = 100,
    ) -> list[ArtifactMetadata]:
        """List artifacts."""
        result = []
        
        for meta_file in self.storage_path.glob("*.meta.json"):
            artifact_id = meta_file.stem.replace(".meta", "")
            
            if prefix and not artifact_id.startswith(prefix):
                continue
            
            try:
                metadata = self.get_metadata(artifact_id)
                result.append(metadata)
            except Exception:
                continue
            
            if len(result) >= limit:
                break
        
        return result
