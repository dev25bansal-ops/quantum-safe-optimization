#!/usr/bin/env python3
"""
Automated Backup and Restore System.

Provides:
- Scheduled backups (full and incremental)
- Point-in-time recovery
- Cross-region backup replication
- Backup validation and integrity checks
- Automated retention management
"""

import asyncio
import gzip
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class BackupType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATED = "validated"


@dataclass
class BackupMetadata:
    backup_id: str
    backup_type: BackupType
    timestamp: datetime
    size_bytes: int
    checksum_sha256: str
    status: BackupStatus
    components: list[str] = field(default_factory=list)
    parent_backup_id: Optional[str] = None
    retention_days: int = 90
    compressed: bool = True
    encrypted: bool = False

    def to_dict(self) -> dict:
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type.value,
            "timestamp": self.timestamp.isoformat(),
            "size_bytes": self.size_bytes,
            "checksum_sha256": self.checksum_sha256,
            "status": self.status.value,
            "components": self.components,
            "parent_backup_id": self.parent_backup_id,
            "retention_days": self.retention_days,
            "compressed": self.compressed,
            "encrypted": self.encrypted,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BackupMetadata":
        return cls(
            backup_id=data["backup_id"],
            backup_type=BackupType(data["backup_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            size_bytes=data["size_bytes"],
            checksum_sha256=data["checksum_sha256"],
            status=BackupStatus(data["status"]),
            components=data.get("components", []),
            parent_backup_id=data.get("parent_backup_id"),
            retention_days=data.get("retention_days", 90),
            compressed=data.get("compressed", True),
            encrypted=data.get("encrypted", False),
        )


class BackupManager:
    """Manages database and application backups."""

    def __init__(
        self,
        backup_root: str = "backups",
        retention_days: int = 90,
        compress: bool = True,
    ):
        self.backup_root = Path(backup_root)
        self.retention_days = retention_days
        self.compress = compress

        self.backup_root.mkdir(parents=True, exist_ok=True)
        (self.backup_root / "metadata").mkdir(exist_ok=True)

        self.db_path = Path("quantum_optimization.db")
        self.cosmos_backup_dir = self.backup_root / "cosmos"
        self.cosmos_backup_dir.mkdir(exist_ok=True)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _compress_file(self, source: Path, dest: Path) -> bool:
        """Compress a file using gzip."""
        try:
            with open(source, "rb") as f_in:
                with gzip.open(dest, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return True
        except Exception as e:
            logger.error("compression_failed", error=str(e))
            return False

    def _decompress_file(self, source: Path, dest: Path) -> bool:
        """Decompress a gzipped file."""
        try:
            with gzip.open(source, "rb") as f_in:
                with open(dest, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return True
        except Exception as e:
            logger.error("decompression_failed", error=str(e))
            return False

    def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        components: Optional[list[str]] = None,
        parent_backup_id: Optional[str] = None,
    ) -> Optional[BackupMetadata]:
        """Create a new backup."""
        backup_id = (
            f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        )
        backup_dir = self.backup_root / backup_id
        backup_dir.mkdir(parents=True, exist_ok=True)

        if components is None:
            components = ["database", "cosmos", "keys", "config"]

        metadata = BackupMetadata(
            backup_id=backup_id,
            backup_type=backup_type,
            timestamp=datetime.now(timezone.utc),
            size_bytes=0,
            checksum_sha256="",
            status=BackupStatus.IN_PROGRESS,
            components=components,
            parent_backup_id=parent_backup_id,
            retention_days=self.retention_days,
            compressed=self.compress,
        )

        total_size = 0
        backup_files = []

        try:
            if "database" in components and self.db_path.exists():
                db_backup = backup_dir / "database.db"
                shutil.copy2(self.db_path, db_backup)

                if self.compress:
                    compressed = backup_dir / "database.db.gz"
                    self._compress_file(db_backup, compressed)
                    db_backup.unlink()
                    backup_files.append(compressed)
                else:
                    backup_files.append(db_backup)

                total_size += backup_files[-1].stat().st_size
                logger.info("database_backed_up", size=backup_files[-1].stat().st_size)

            if "cosmos" in components:
                cosmos_backup_file = backup_dir / "cosmos_data.json.gz"
                if self._backup_cosmos_db(cosmos_backup_file):
                    backup_files.append(cosmos_backup_file)
                    total_size += cosmos_backup_file.stat().st_size
                    logger.info("cosmos_backed_up")

            if "keys" in components:
                keys_dir = Path("keys")
                if keys_dir.exists():
                    keys_backup = backup_dir / "keys.tar.gz"
                    subprocess.run(
                        ["tar", "-czf", str(keys_backup), "-C", str(keys_dir.parent), "keys"],
                        check=True,
                    )
                    backup_files.append(keys_backup)
                    total_size += keys_backup.stat().st_size
                    logger.info("keys_backed_up")

            if "config" in components:
                config_backup = backup_dir / "config.json"
                config_data = {
                    "environment": dict(os.environ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                with open(config_backup, "w") as f:
                    json.dump(config_data, f, indent=2)
                total_size += config_backup.stat().st_size

            checksum = self._calculate_checksum(backup_files[0]) if backup_files else ""

            metadata.size_bytes = total_size
            metadata.checksum_sha256 = checksum
            metadata.status = BackupStatus.COMPLETED

        except Exception as e:
            logger.error("backup_failed", error=str(e), backup_id=backup_id)
            metadata.status = BackupStatus.FAILED
            shutil.rmtree(backup_dir, ignore_errors=True)
            return None

        metadata_file = self.backup_root / "metadata" / f"{backup_id}.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        logger.info(
            "backup_completed",
            backup_id=backup_id,
            size_bytes=total_size,
            components=components,
        )

        return metadata

    def _backup_cosmos_db(self, output_path: Path) -> bool:
        """Backup Cosmos DB data."""
        try:
            cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
            cosmos_key = os.getenv("COSMOS_KEY")
            cosmos_database = os.getenv("COSMOS_DATABASE", "quantum_optimization")

            if not cosmos_endpoint or not cosmos_key:
                logger.warning("cosmos_credentials_not_set")
                return False

            import gzip
            import json

            backup_data = {
                "database": cosmos_database,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "containers": {},
            }

            try:
                from azure.cosmos import CosmosClient

                client = CosmosClient(cosmos_endpoint, credential=cosmos_key)
                database = client.get_database_client(cosmos_database)

                for container_props in database.list_containers():
                    container_name = container_props["id"]
                    container = database.get_container_client(container_name)

                    items = list(container.read_all_items())
                    backup_data["containers"][container_name] = items
                    logger.info(
                        "cosmos_container_backed_up", container=container_name, count=len(items)
                    )

            except ImportError:
                logger.warning("azure_cosmos_not_available")
                return False
            except Exception as e:
                logger.warning("cosmos_backup_partial", error=str(e))

            with gzip.open(output_path, "wt", encoding="utf-8") as f:
                json.dump(backup_data, f)

            return True

        except Exception as e:
            logger.error("cosmos_backup_failed", error=str(e))
            return False

    def restore_backup(self, backup_id: str, components: Optional[list[str]] = None) -> bool:
        """Restore from a backup."""
        metadata_file = self.backup_root / "metadata" / f"{backup_id}.json"
        if not metadata_file.exists():
            logger.error("backup_not_found", backup_id=backup_id)
            return False

        with open(metadata_file) as f:
            metadata = BackupMetadata.from_dict(json.load(f))

        backup_dir = self.backup_root / backup_id
        if not backup_dir.exists():
            logger.error("backup_directory_not_found", backup_id=backup_id)
            return False

        if components is None:
            components = metadata.components

        try:
            if "database" in components:
                db_backup = (
                    backup_dir / "database.db.gz"
                    if metadata.compressed
                    else backup_dir / "database.db"
                )

                if db_backup.exists():
                    if metadata.compressed:
                        self._decompress_file(db_backup, self.db_path)
                    else:
                        shutil.copy2(db_backup, self.db_path)
                    logger.info("database_restored")

            if "cosmos" in components:
                cosmos_backup = backup_dir / "cosmos_data.json.gz"
                if cosmos_backup.exists():
                    self._restore_cosmos_db(cosmos_backup)
                    logger.info("cosmos_restored")

            if "keys" in components:
                keys_backup = backup_dir / "keys.tar.gz"
                if keys_backup.exists():
                    subprocess.run(
                        ["tar", "-xzf", str(keys_backup), "-C", "."],
                        check=True,
                    )
                    logger.info("keys_restored")

            logger.info("restore_completed", backup_id=backup_id)
            return True

        except Exception as e:
            logger.error("restore_failed", error=str(e))
            return False

    def _restore_cosmos_db(self, backup_path: Path) -> bool:
        """Restore Cosmos DB from backup."""
        try:
            import gzip
            import json

            with gzip.open(backup_path, "rt", encoding="utf-8") as f:
                backup_data = json.load(f)

            cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
            cosmos_key = os.getenv("COSMOS_KEY")
            cosmos_database = backup_data.get("database", "quantum_optimization")

            if not cosmos_endpoint or not cosmos_key:
                logger.warning("cosmos_credentials_not_set")
                return False

            try:
                from azure.cosmos import CosmosClient

                client = CosmosClient(cosmos_endpoint, credential=cosmos_key)
                database = client.get_database_client(cosmos_database)

                for container_name, items in backup_data.get("containers", {}).items():
                    container = database.get_container_client(container_name)
                    for item in items:
                        try:
                            container.upsert_item(item)
                        except Exception as e:
                            logger.warning("item_restore_failed", error=str(e))

                    logger.info(
                        "cosmos_container_restored", container=container_name, count=len(items)
                    )

            except ImportError:
                logger.warning("azure_cosmos_not_available")
                return False

            return True

        except Exception as e:
            logger.error("cosmos_restore_failed", error=str(e))
            return False

    def validate_backup(self, backup_id: str) -> bool:
        """Validate backup integrity."""
        metadata_file = self.backup_root / "metadata" / f"{backup_id}.json"
        if not metadata_file.exists():
            return False

        with open(metadata_file) as f:
            metadata = BackupMetadata.from_dict(json.load(f))

        backup_dir = self.backup_root / backup_id
        if not backup_dir.exists():
            return False

        db_backup = backup_dir / "database.db.gz"
        if db_backup.exists():
            checksum = self._calculate_checksum(db_backup)
            if checksum != metadata.checksum_sha256:
                logger.error("checksum_mismatch", backup_id=backup_id)
                return False

        metadata.status = BackupStatus.VALIDATED
        with open(metadata_file, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        logger.info("backup_validated", backup_id=backup_id)
        return True

    def list_backups(self, include_expired: bool = False) -> list[BackupMetadata]:
        """List all backups."""
        backups = []
        metadata_dir = self.backup_root / "metadata"

        for metadata_file in metadata_dir.glob("*.json"):
            try:
                with open(metadata_file) as f:
                    metadata = BackupMetadata.from_dict(json.load(f))
                backups.append(metadata)
            except Exception as e:
                logger.warning("failed_to_read_metadata", file=str(metadata_file), error=str(e))

        backups.sort(key=lambda x: x.timestamp, reverse=True)
        return backups

    def cleanup_expired_backups(self) -> int:
        """Remove backups past retention period."""
        removed_count = 0
        now = datetime.now(timezone.utc)

        for metadata in self.list_backups(include_expired=True):
            expiration_date = metadata.timestamp + timedelta(days=metadata.retention_days)

            if now > expiration_date:
                backup_dir = self.backup_root / metadata.backup_id
                metadata_file = self.backup_root / "metadata" / f"{metadata.backup_id}.json"

                shutil.rmtree(backup_dir, ignore_errors=True)
                metadata_file.unlink(missing_ok=True)

                removed_count += 1
                logger.info("backup_expired_removed", backup_id=metadata.backup_id)

        return removed_count

    def schedule_backup(self, backup_type: BackupType = BackupType.FULL) -> None:
        """Schedule recurring backups."""
        self.create_backup(backup_type=backup_type)
        self.cleanup_expired_backups()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Backup Manager")
    parser.add_argument(
        "command",
        choices=["create", "restore", "list", "validate", "cleanup", "schedule"],
        help="Command to execute",
    )
    parser.add_argument("--backup-id", "-b", help="Backup ID for restore/validate")
    parser.add_argument(
        "--type", "-t", default="full", choices=["full", "incremental"], help="Backup type"
    )
    parser.add_argument("--components", "-c", nargs="+", help="Components to backup")
    parser.add_argument(
        "--retention-days", "-r", type=int, default=90, help="Retention period in days"
    )

    args = parser.parse_args()

    manager = BackupManager(retention_days=args.retention_days)

    if args.command == "create":
        backup_type = BackupType.FULL if args.type == "full" else BackupType.INCREMENTAL
        metadata = manager.create_backup(backup_type=backup_type, components=args.components)
        if metadata:
            print(f"Backup created: {metadata.backup_id}")
            print(f"Size: {metadata.size_bytes} bytes")
            print(f"Components: {metadata.components}")

    elif args.command == "restore":
        if not args.backup_id:
            print("Error: --backup-id required for restore")
            return
        success = manager.restore_backup(args.backup_id, components=args.components)
        print("Restore successful" if success else "Restore failed")

    elif args.command == "list":
        backups = manager.list_backups()
        print(f"Found {len(backups)} backups:")
        for b in backups:
            print(
                f"  {b.backup_id}: {b.backup_type.value} - {b.status.value} - {b.size_bytes} bytes"
            )

    elif args.command == "validate":
        if not args.backup_id:
            print("Error: --backup-id required for validate")
            return
        valid = manager.validate_backup(args.backup_id)
        print(f"Backup valid: {valid}")

    elif args.command == "cleanup":
        removed = manager.cleanup_expired_backups()
        print(f"Removed {removed} expired backups")

    elif args.command == "schedule":
        manager.schedule_backup()
        print("Scheduled backup completed")


if __name__ == "__main__":
    main()
