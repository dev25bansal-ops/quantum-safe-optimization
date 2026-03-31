#!/usr/bin/env python3
"""
QSOP Admin CLI Tool.

Management commands for the Quantum-Safe Optimization Platform.

Usage:
    python admin.py users list
    python admin.py users create --username admin --password secret
    python admin.py keys generate --type kem --level 3
    python admin.py jobs list --status pending
    python admin.py migrate up
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_db():
    """Setup database connection."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    database_url = os.getenv("DATABASE_URL", "sqlite:///./quantum_optimization.db")
    engine = create_engine(database_url)
    return sessionmaker(bind=engine)()


def cmd_users_list(args):
    """List all users."""
    print("\n=== Users ===")
    print(f"{'ID':<36} {'Username':<20} {'Email':<30} {'Roles':<20} {'Active'}")
    print("-" * 120)

    try:
        from api.routers.auth import _users_db

        for user in _users_db.values():
            print(
                f"{user.get('user_id', 'N/A'):<36} "
                f"{user.get('username', 'N/A'):<20} "
                f"{user.get('email', 'N/A') or 'N/A':<30} "
                f"{','.join(user.get('roles', [])):<20} "
                f"{'Yes' if user.get('is_active', True) else 'No'}"
            )
    except Exception as e:
        print(f"Error: {e}")


def cmd_users_create(args):
    """Create a new user."""
    from api.routers.auth import hash_password, _users_db

    user_id = f"usr_{os.urandom(8).hex()}"

    user = {
        "user_id": user_id,
        "id": user_id,
        "username": args.username,
        "password_hash": hash_password(args.password),
        "email": args.email,
        "roles": args.roles.split(",") if args.roles else ["user"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
    }

    _users_db[args.username] = user
    print(f"Created user: {args.username} (ID: {user_id})")


def cmd_users_delete(args):
    """Delete a user."""
    from api.routers.auth import _users_db

    if args.username in _users_db:
        del _users_db[args.username]
        print(f"Deleted user: {args.username}")
    else:
        print(f"User not found: {args.username}")


def cmd_keys_generate(args):
    """Generate a new PQC key pair."""
    from quantum_safe_crypto import KemKeyPair, SigningKeyPair

    key_type = args.type or "kem"
    level = args.level or 3

    print(f"\nGenerating {key_type.upper()} key (Level {level})...")

    if key_type == "kem":
        keypair = KemKeyPair(security_level=level)
        algorithm = keypair.algorithm
    elif key_type == "signing":
        keypair = SigningKeyPair(security_level=level)
        algorithm = keypair.algorithm
    else:
        print(f"Unknown key type: {key_type}")
        return

    print(f"\nAlgorithm: {algorithm}")
    print(f"\nPublic Key (base64):")
    print(keypair.public_key[:100] + "..." if len(keypair.public_key) > 100 else keypair.public_key)
    print(f"\nKey Length: {len(keypair.public_key)} bytes")


def cmd_keys_list(args):
    """List all keys."""
    print("\n=== PQC Keys ===")
    print(f"{'Key ID':<36} {'Type':<10} {'Algorithm':<15} {'Level':<6} {'Status'}")
    print("-" * 80)


def cmd_jobs_list(args):
    """List jobs."""
    from api.routers.jobs import _jobs_db

    status_filter = args.status

    print("\n=== Jobs ===")
    print(f"{'ID':<36} {'Type':<10} {'Status':<12} {'User':<20} {'Created'}")
    print("-" * 100)

    count = 0
    for job in _jobs_db.values():
        if status_filter and job.get("status") != status_filter:
            continue

        print(
            f"{job.get('id', 'N/A'):<36} "
            f"{job.get('problem_type', 'N/A'):<10} "
            f"{job.get('status', 'N/A'):<12} "
            f"{job.get('user_id', 'system') or 'system':<20} "
            f"{job.get('created_at', 'N/A')[:19] or 'N/A'}"
        )
        count += 1

    print(f"\nTotal: {count} jobs")


def cmd_jobs_cancel(args):
    """Cancel a job."""
    from api.routers.jobs import _jobs_db

    job_id = args.job_id

    if job_id not in _jobs_db:
        print(f"Job not found: {job_id}")
        return

    job = _jobs_db[job_id]
    if job.get("status") in ["completed", "failed", "cancelled"]:
        print(f"Cannot cancel job with status: {job.get('status')}")
        return

    job["status"] = "cancelled"
    print(f"Cancelled job: {job_id}")


def cmd_migrate_up(args):
    """Run database migrations."""
    print("Running migrations...")
    os.system("alembic upgrade head")


def cmd_migrate_down(args):
    """Rollback database migrations."""
    print("Rolling back migration...")
    os.system("alembic downgrade -1")


def cmd_migrate_status(args):
    """Show migration status."""
    os.system("alembic current")


def cmd_health(args):
    """Check system health."""
    import httpx

    base_url = args.url or "http://localhost:8000"

    print(f"\nChecking health at {base_url}...")

    try:
        response = httpx.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\nStatus: {data.get('status', 'unknown')}")
            print(f"Version: {data.get('version', 'unknown')}")
            print(f"Environment: {data.get('env', 'unknown')}")
        else:
            print(f"Health check failed: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to API: {e}")


def cmd_crypto_status(args):
    """Check crypto status."""
    from quantum_safe_crypto import get_crypto_status

    status = get_crypto_status()
    print("\n=== Crypto Status ===")
    for key, value in status.items():
        print(f"{key}: {value}")


def main():
    parser = argparse.ArgumentParser(
        description="QSOP Admin CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Users commands
    users_parser = subparsers.add_parser("users", help="User management")
    users_sub = users_parser.add_subparsers(dest="subcommand")

    users_list = users_sub.add_parser("list", help="List users")
    users_list.set_defaults(func=cmd_users_list)

    users_create = users_sub.add_parser("create", help="Create user")
    users_create.add_argument("--username", required=True)
    users_create.add_argument("--password", required=True)
    users_create.add_argument("--email")
    users_create.add_argument("--roles", default="user")
    users_create.set_defaults(func=cmd_users_create)

    users_delete = users_sub.add_parser("delete", help="Delete user")
    users_delete.add_argument("username")
    users_delete.set_defaults(func=cmd_users_delete)

    # Keys commands
    keys_parser = subparsers.add_parser("keys", help="Key management")
    keys_sub = keys_parser.add_subparsers(dest="subcommand")

    keys_generate = keys_sub.add_parser("generate", help="Generate key")
    keys_generate.add_argument("--type", choices=["kem", "signing"], default="kem")
    keys_generate.add_argument("--level", type=int, choices=[1, 3, 5], default=3)
    keys_generate.set_defaults(func=cmd_keys_generate)

    keys_list = keys_sub.add_parser("list", help="List keys")
    keys_list.set_defaults(func=cmd_keys_list)

    # Jobs commands
    jobs_parser = subparsers.add_parser("jobs", help="Job management")
    jobs_sub = jobs_parser.add_subparsers(dest="subcommand")

    jobs_list = jobs_sub.add_parser("list", help="List jobs")
    jobs_list.add_argument("--status", help="Filter by status")
    jobs_list.set_defaults(func=cmd_jobs_list)

    jobs_cancel = jobs_sub.add_parser("cancel", help="Cancel job")
    jobs_cancel.add_argument("job_id")
    jobs_cancel.set_defaults(func=cmd_jobs_cancel)

    # Migrate commands
    migrate_parser = subparsers.add_parser("migrate", help="Database migrations")
    migrate_sub = migrate_parser.add_subparsers(dest="subcommand")

    migrate_up = migrate_sub.add_parser("up", help="Run migrations")
    migrate_up.set_defaults(func=cmd_migrate_up)

    migrate_down = migrate_sub.add_parser("down", help="Rollback migration")
    migrate_down.set_defaults(func=cmd_migrate_down)

    migrate_status = migrate_sub.add_parser("status", help="Migration status")
    migrate_status.set_defaults(func=cmd_migrate_status)

    # Health command
    health_parser = subparsers.add_parser("health", help="Health check")
    health_parser.add_argument("--url", help="API URL")
    health_parser.set_defaults(func=cmd_health)

    # Crypto command
    crypto_parser = subparsers.add_parser("crypto", help="Crypto status")
    crypto_sub = crypto_parser.add_subparsers(dest="subcommand")
    crypto_status = crypto_sub.add_parser("status", help="Crypto status")
    crypto_status.set_defaults(func=cmd_crypto_status)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
