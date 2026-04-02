#!/usr/bin/env python3
"""
Automated Database Migration Script.

Handles database migrations with Alembic including:
- Automatic migration generation
- Safe migration execution with rollback
- Pre-migration backups
- Migration validation
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


class MigrationManager:
    """Manages database migrations with safety checks."""

    def __init__(self, alembic_ini: str = "alembic.ini"):
        self.alembic_ini = alembic_ini
        self.backup_dir = Path("backups/migrations")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def run_alembic(self, *args: str) -> tuple[int, str, str]:
        """Run alembic command and return exit code, stdout, stderr."""
        cmd = ["alembic", "-c", self.alembic_ini] + list(args)
        logger.info("running_alembic_command", command=" ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr

    def get_current_revision(self) -> Optional[str]:
        """Get current database revision."""
        code, stdout, stderr = self.run_alembic("current")
        if code != 0:
            logger.error("failed_to_get_revision", stderr=stderr)
            return None

        for line in stdout.split("\n"):
            if line.strip() and not line.startswith("INFO"):
                parts = line.split()
                if parts:
                    return parts[0]
        return None

    def get_pending_migrations(self) -> list[str]:
        """Get list of pending migrations."""
        code, stdout, stderr = self.run_alembic("history", "--verbose")
        if code != 0:
            return []

        pending = []
        current = self.get_current_revision()
        for line in stdout.split("\n"):
            if " -> " in line and current and current not in line:
                parts = line.split("->")
                if len(parts) >= 2:
                    pending.append(parts[1].strip().split()[0])
        return pending

    def backup_before_migration(self) -> Optional[Path]:
        """Create database backup before migration."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        db_path = Path("quantum_optimization.db")

        if not db_path.exists():
            logger.info("no_database_to_backup")
            return None

        backup_path = self.backup_dir / f"pre_migration_{timestamp}.db"

        import shutil

        shutil.copy2(db_path, backup_path)
        logger.info("database_backed_up", path=str(backup_path))
        return backup_path

    def generate_migration(self, message: str) -> bool:
        """Generate a new migration."""
        code, stdout, stderr = self.run_alembic("revision", "--autogenerate", "-m", message)

        if code != 0:
            logger.error("migration_generation_failed", stderr=stderr)
            return False

        logger.info("migration_generated", output=stdout)
        return True

    def upgrade(self, revision: str = "head") -> bool:
        """Upgrade database to revision."""
        logger.info("starting_migration_upgrade", target=revision)

        backup_path = self.backup_before_migration()

        code, stdout, stderr = self.run_alembic("upgrade", revision)

        if code != 0:
            logger.error("migration_upgrade_failed", stderr=stderr)
            if backup_path:
                logger.warning("backup_available_for_rollback", path=str(backup_path))
            return False

        logger.info("migration_upgrade_complete", output=stdout)
        return True

    def downgrade(self, revision: str = "-1") -> bool:
        """Downgrade database by one revision."""
        logger.warning("starting_migration_downgrade", target=revision)

        backup_path = self.backup_before_migration()

        code, stdout, stderr = self.run_alembic("downgrade", revision)

        if code != 0:
            logger.error("migration_downgrade_failed", stderr=stderr)
            return False

        logger.info("migration_downgrade_complete", output=stdout)
        return True

    def rollback_to_backup(self, backup_path: Path) -> bool:
        """Rollback database to a backup."""
        db_path = Path("quantum_optimization.db")

        if not backup_path.exists():
            logger.error("backup_not_found", path=str(backup_path))
            return False

        import shutil

        shutil.copy2(backup_path, db_path)
        logger.info("database_restored_from_backup", path=str(backup_path))
        return True

    def validate_migration(self) -> bool:
        """Validate migration integrity."""
        code, stdout, stderr = self.run_alembic("check")

        if code != 0:
            logger.error("migration_validation_failed", stderr=stderr)
            return False

        logger.info("migration_validation_passed")
        return True

    def get_migration_status(self) -> dict:
        """Get detailed migration status."""
        current = self.get_current_revision()
        pending = self.get_pending_migrations()

        code, stdout, stderr = self.run_alembic("history")

        return {
            "current_revision": current,
            "pending_migrations": pending,
            "pending_count": len(pending),
            "history": stdout if code == 0 else stderr,
            "backup_dir": str(self.backup_dir),
        }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Database Migration Manager")
    parser.add_argument(
        "command",
        choices=["status", "upgrade", "downgrade", "generate", "validate", "backup"],
        help="Command to execute",
    )
    parser.add_argument("--message", "-m", help="Migration message for generate")
    parser.add_argument("--revision", "-r", default="head", help="Target revision")

    args = parser.parse_args()

    manager = MigrationManager()

    if args.command == "status":
        status = manager.get_migration_status()
        print(f"Current Revision: {status['current_revision']}")
        print(f"Pending Migrations: {status['pending_count']}")
        print(f"Backup Directory: {status['backup_dir']}")

    elif args.command == "upgrade":
        success = manager.upgrade(args.revision)
        sys.exit(0 if success else 1)

    elif args.command == "downgrade":
        success = manager.downgrade(args.revision)
        sys.exit(0 if success else 1)

    elif args.command == "generate":
        if not args.message:
            print("Error: --message required for generate")
            sys.exit(1)
        success = manager.generate_migration(args.message)
        sys.exit(0 if success else 1)

    elif args.command == "validate":
        success = manager.validate_migration()
        sys.exit(0 if success else 1)

    elif args.command == "backup":
        backup_path = manager.backup_before_migration()
        if backup_path:
            print(f"Backup created: {backup_path}")
        else:
            print("No database to backup")


if __name__ == "__main__":
    main()
