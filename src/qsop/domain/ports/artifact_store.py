"""
Artifact store port definition.

Defines the protocol for storing and retrieving job artifacts
including circuits, parameter snapshots, and encrypted blobs.
"""

from typing import Protocol, runtime_checkable
from uuid import UUID

from qsop.domain.models.artifacts import (
    ArtifactType,
    CircuitArtifact,
    EncryptedBlob,
    ParameterSnapshot,
)


@runtime_checkable
class ArtifactStore(Protocol):
    """
    Protocol for artifact storage and retrieval.

    Provides persistent storage for job artifacts including quantum circuits,
    parameter snapshots, and encrypted data blobs.
    """

    def store_blob(self, blob: EncryptedBlob) -> UUID:
        """
        Store an encrypted blob.

        Args:
            blob: The encrypted blob to store.

        Returns:
            The blob ID.

        Raises:
            ArtifactError: If storage fails.
        """
        ...

    def get_blob(self, blob_id: UUID) -> EncryptedBlob:
        """
        Retrieve an encrypted blob.

        Args:
            blob_id: The blob identifier.

        Returns:
            The encrypted blob.

        Raises:
            ArtifactError: If blob not found or retrieval fails.
        """
        ...

    def delete_blob(self, blob_id: UUID) -> None:
        """
        Delete an encrypted blob.

        Args:
            blob_id: The blob identifier.

        Raises:
            ArtifactError: If deletion fails.
        """
        ...

    def store_circuit(self, circuit: CircuitArtifact) -> UUID:
        """
        Store a circuit artifact.

        Args:
            circuit: The circuit artifact to store.

        Returns:
            The artifact ID.

        Raises:
            ArtifactError: If storage fails.
        """
        ...

    def get_circuit(self, artifact_id: UUID) -> CircuitArtifact:
        """
        Retrieve a circuit artifact.

        Args:
            artifact_id: The artifact identifier.

        Returns:
            The circuit artifact.

        Raises:
            ArtifactError: If artifact not found or retrieval fails.
        """
        ...

    def list_circuits(self, job_id: UUID) -> list[CircuitArtifact]:
        """
        List all circuit artifacts for a job.

        Args:
            job_id: The job identifier.

        Returns:
            List of circuit artifacts.

        Raises:
            ArtifactError: If listing fails.
        """
        ...

    def delete_circuit(self, artifact_id: UUID) -> None:
        """
        Delete a circuit artifact.

        Also deletes associated encrypted blobs.

        Args:
            artifact_id: The artifact identifier.

        Raises:
            ArtifactError: If deletion fails.
        """
        ...

    def store_snapshot(self, snapshot: ParameterSnapshot) -> UUID:
        """
        Store a parameter snapshot.

        Args:
            snapshot: The parameter snapshot to store.

        Returns:
            The snapshot ID.

        Raises:
            ArtifactError: If storage fails.
        """
        ...

    def get_snapshot(self, snapshot_id: UUID) -> ParameterSnapshot:
        """
        Retrieve a parameter snapshot.

        Args:
            snapshot_id: The snapshot identifier.

        Returns:
            The parameter snapshot.

        Raises:
            ArtifactError: If snapshot not found or retrieval fails.
        """
        ...

    def list_snapshots(
        self,
        job_id: UUID,
        start_iteration: int | None = None,
        end_iteration: int | None = None,
    ) -> list[ParameterSnapshot]:
        """
        List parameter snapshots for a job.

        Args:
            job_id: The job identifier.
            start_iteration: Optional start iteration (inclusive).
            end_iteration: Optional end iteration (inclusive).

        Returns:
            List of parameter snapshots sorted by iteration.

        Raises:
            ArtifactError: If listing fails.
        """
        ...

    def delete_snapshot(self, snapshot_id: UUID) -> None:
        """
        Delete a parameter snapshot.

        Args:
            snapshot_id: The snapshot identifier.

        Raises:
            ArtifactError: If deletion fails.
        """
        ...

    def delete_job_artifacts(self, job_id: UUID) -> int:
        """
        Delete all artifacts associated with a job.

        Args:
            job_id: The job identifier.

        Returns:
            Number of artifacts deleted.

        Raises:
            ArtifactError: If deletion fails.
        """
        ...

    def get_artifact_count(
        self,
        job_id: UUID | None = None,
        artifact_type: ArtifactType | None = None,
    ) -> int:
        """
        Count artifacts matching criteria.

        Args:
            job_id: Optional filter by job.
            artifact_type: Optional filter by type.

        Returns:
            Number of matching artifacts.

        Raises:
            ArtifactError: If count fails.
        """
        ...

    def get_total_size_bytes(self, job_id: UUID | None = None) -> int:
        """
        Get total storage size for artifacts.

        Args:
            job_id: Optional filter by job.

        Returns:
            Total size in bytes.

        Raises:
            ArtifactError: If calculation fails.
        """
        ...
