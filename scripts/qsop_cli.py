#!/usr/bin/env python3
"""
QSOP Command Line Interface.

Provides command-line access to the Quantum-Safe Optimization Platform.

Usage:
    qsop jobs list                    # List all jobs
    qsop jobs submit <config.json>    # Submit a new job
    qsop jobs status <job_id>         # Get job status
    qsop jobs cancel <job_id>         # Cancel a job
    qsop backends list                # List available backends
    qsop backends test <backend_id>   # Test backend connection
    qsop auth login                   # Login to platform
    qsop auth logout                  # Logout
    qsop keys generate                # Generate PQC key pair
    qsop templates list               # List job templates
    qsop alerts list                  # List active alerts
    qsop config set <key> <value>     # Set configuration
    qsop config get <key>             # Get configuration
    qsop status                       # Show platform status
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CONFIG_FILE = Path.home() / ".qsop" / "config.json"
DEFAULT_BASE_URL = os.getenv("QSOP_API_URL", "http://localhost:8000")


def load_config() -> dict[str, Any]:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"base_url": DEFAULT_BASE_URL}


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_client(config: dict[str, Any]) -> httpx.AsyncClient:
    """Get an authenticated HTTP client."""
    headers = {"Content-Type": "application/json"}
    if token := config.get("token"):
        headers["Authorization"] = f"Bearer {token}"

    return httpx.AsyncClient(
        base_url=config.get("base_url", DEFAULT_BASE_URL),
        headers=headers,
        timeout=60.0,
    )


async def cmd_login(args: argparse.Namespace) -> int:
    """Login to the platform."""
    config = load_config()

    username = args.username or input("Username: ")
    import getpass

    password = args.password or getpass.getpass("Password: ")

    async with get_client(config) as client:
        try:
            response = await client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": password},
            )
            response.raise_for_status()
            data = response.json()

            config["token"] = data["access_token"]
            config["username"] = username
            save_config(config)

            print(f"✓ Logged in as {username}")
            print(f"  Token expires in {data.get('expires_in', 86400) // 3600} hours")
            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Login failed: {e.response.status_code} - {e.response.text}", file=sys.stderr)
            return 1


async def cmd_logout(args: argparse.Namespace) -> int:
    """Logout from the platform."""
    config = load_config()

    if "token" not in config:
        print("Not logged in")
        return 0

    async with get_client(config) as client:
        try:
            await client.post("/api/v1/auth/logout")
        except Exception:
            pass

    config.pop("token", None)
    config.pop("username", None)
    save_config(config)

    print("✓ Logged out")
    return 0


async def cmd_jobs_list(args: argparse.Namespace) -> int:
    """List all jobs."""
    config = load_config()

    async with get_client(config) as client:
        try:
            response = await client.get("/api/v1/jobs", params={"limit": args.limit})
            response.raise_for_status()
            data = response.json()

            jobs = data.get("jobs", [])
            if not jobs:
                print("No jobs found")
                return 0

            print(f"Found {data.get('total', len(jobs))} jobs:\n")
            print(f"{'ID':<20} {'Type':<10} {'Status':<10} {'Created':<20}")
            print("-" * 60)

            for job in jobs:
                print(
                    f"{job['id'][:20]:<20} {job.get('problem_type', 'N/A'):<10} "
                    f"{job['status']:<10} {job.get('created_at', 'N/A')[:19]}"
                )

            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Failed to list jobs: {e.response.status_code}", file=sys.stderr)
            return 1


async def cmd_jobs_submit(args: argparse.Namespace) -> int:
    """Submit a new job."""
    config = load_config()

    if not Path(args.config).exists():
        print(f"✗ Config file not found: {args.config}", file=sys.stderr)
        return 1

    with open(args.config, "r") as f:
        job_config = json.load(f)

    async with get_client(config) as client:
        try:
            response = await client.post("/api/v1/jobs", json=job_config)
            response.raise_for_status()
            job = response.json()

            print(f"✓ Job submitted successfully")
            print(f"  ID: {job['id']}")
            print(f"  Status: {job['status']}")
            print(f"  Use: qsop jobs status {job['id']}")

            return 0

        except httpx.HTTPStatusError as e:
            print(
                f"✗ Failed to submit job: {e.response.status_code} - {e.response.text}",
                file=sys.stderr,
            )
            return 1


async def cmd_jobs_status(args: argparse.Namespace) -> int:
    """Get job status."""
    config = load_config()

    async with get_client(config) as client:
        try:
            response = await client.get(f"/api/v1/jobs/{args.job_id}")
            response.raise_for_status()
            job = response.json()

            print(f"Job: {job['id']}")
            print(f"Status: {job['status']}")
            print(f"Type: {job.get('problem_type', 'N/A')}")
            print(f"Backend: {job.get('backend', 'N/A')}")
            print(f"Created: {job.get('created_at', 'N/A')}")

            if job["status"] == "completed":
                print(f"\nResult available. Use: qsop jobs result {job['id']}")
            elif job["status"] == "failed":
                print(f"\nError: {job.get('error', 'Unknown error')}")

            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Failed to get job status: {e.response.status_code}", file=sys.stderr)
            return 1


async def cmd_jobs_result(args: argparse.Namespace) -> int:
    """Get job result."""
    config = load_config()

    async with get_client(config) as client:
        try:
            response = await client.get(f"/api/v1/jobs/{args.job_id}/result")
            response.raise_for_status()
            result = response.json()

            if args.output:
                with open(args.output, "w") as f:
                    json.dump(result, f, indent=2)
                print(f"✓ Result saved to {args.output}")
            else:
                print(json.dumps(result, indent=2))

            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Failed to get job result: {e.response.status_code}", file=sys.stderr)
            return 1


async def cmd_jobs_cancel(args: argparse.Namespace) -> int:
    """Cancel a job."""
    config = load_config()

    async with get_client(config) as client:
        try:
            response = await client.delete(f"/api/v1/jobs/{args.job_id}")
            response.raise_for_status()

            print(f"✓ Job {args.job_id} cancelled")
            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Failed to cancel job: {e.response.status_code}", file=sys.stderr)
            return 1


async def cmd_backends_list(args: argparse.Namespace) -> int:
    """List available backends."""
    config = load_config()

    async with get_client(config) as client:
        try:
            response = await client.get("/api/v1/backends")
            response.raise_for_status()
            backends = response.json()

            print("Available Backends:\n")
            print(f"{'ID':<20} {'Type':<15} {'Status':<10} {'Qubits':<8}")
            print("-" * 55)

            for backend in backends.get("backends", []):
                print(
                    f"{backend['id'][:20]:<20} {backend.get('type', 'N/A'):<15} "
                    f"{backend.get('status', 'N/A'):<10} {backend.get('num_qubits', 'N/A'):<8}"
                )

            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Failed to list backends: {e.response.status_code}", file=sys.stderr)
            return 1


async def cmd_templates_list(args: argparse.Namespace) -> int:
    """List job templates."""
    config = load_config()

    async with get_client(config) as client:
        try:
            response = await client.get("/api/v1/templates", params={"limit": args.limit})
            response.raise_for_status()
            data = response.json()

            templates = data.get("templates", [])
            if not templates:
                print("No templates found")
                return 0

            print(f"Found {data.get('total', len(templates))} templates:\n")
            print(f"{'ID':<25} {'Name':<25} {'Category':<15} {'Algorithm':<10}")
            print("-" * 75)

            for tpl in templates:
                print(
                    f"{tpl['id'][:25]:<25} {tpl['name'][:25]:<25} "
                    f"{tpl.get('category', 'N/A'):<15} {tpl.get('algorithm', 'N/A'):<10}"
                )

            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Failed to list templates: {e.response.status_code}", file=sys.stderr)
            return 1


async def cmd_alerts_list(args: argparse.Namespace) -> int:
    """List active alerts."""
    config = load_config()

    async with get_client(config) as client:
        try:
            response = await client.get("/api/v1/alerts/active")
            response.raise_for_status()
            data = response.json()

            alerts = data.get("alerts", [])
            if not alerts:
                print("No active alerts")
                return 0

            print(f"Active Alerts ({len(alerts)}):\n")

            for alert in alerts:
                severity_emoji = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "🔵"}
                emoji = severity_emoji.get(alert.get("severity", "info"), "⚪")
                print(
                    f"{emoji} [{alert.get('severity', 'info').upper()}] {alert.get('rule_name', 'N/A')}"
                )
                print(f"   Metric: {alert.get('metric')} = {alert.get('value')}")
                print(f"   Threshold: {alert.get('threshold')}")
                print(f"   Started: {alert.get('started_at')}\n")

            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Failed to list alerts: {e.response.status_code}", file=sys.stderr)
            return 1


async def cmd_status(args: argparse.Namespace) -> int:
    """Show platform status."""
    config = load_config()

    async with get_client(config) as client:
        try:
            response = await client.get("/health")
            response.raise_for_status()
            health = response.json()

            print("Platform Status:\n")
            print(f"Status: {health.get('status', 'unknown')}")
            print(f"Version: {health.get('version', 'N/A')}")
            print(f"Environment: {health.get('environment', 'N/A')}")
            print(f"Timestamp: {health.get('timestamp', 'N/A')}")

            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Failed to get status: {e.response.status_code}", file=sys.stderr)
            return 1


async def cmd_config_set(args: argparse.Namespace) -> int:
    """Set configuration value."""
    config = load_config()
    config[args.key] = args.value
    save_config(config)
    print(f"✓ Set {args.key} = {args.value}")
    return 0


async def cmd_config_get(args: argparse.Namespace) -> int:
    """Get configuration value."""
    config = load_config()
    if args.key in config:
        print(config[args.key])
        return 0
    else:
        print(f"Key not found: {args.key}", file=sys.stderr)
        return 1


async def cmd_keys_generate(args: argparse.Namespace) -> int:
    """Generate PQC key pair."""
    config = load_config()

    async with get_client(config) as client:
        try:
            response = await client.post("/api/v1/auth/keys/generate")
            response.raise_for_status()
            keys = response.json()

            print("Generated PQC Key Pair:\n")
            print(f"Key ID: {keys.get('key_id')}")
            print(f"Algorithm: {keys.get('algorithm')}")
            print(f"\nPublic Key (base64):")
            print(keys.get("public_key", "N/A")[:80] + "...")
            print(f"\nPrivate Key: {'*' * 40} (shown only once)")

            if args.save:
                key_file = Path(args.save)
                key_file.write_text(json.dumps(keys, indent=2))
                print(f"\n✓ Keys saved to {args.save}")

            return 0

        except httpx.HTTPStatusError as e:
            print(f"✗ Failed to generate keys: {e.response.status_code}", file=sys.stderr)
            return 1


async def async_main(args: argparse.Namespace) -> int:
    """Main async entry point."""
    commands = {
        ("auth", "login"): cmd_login,
        ("auth", "logout"): cmd_logout,
        ("jobs", "list"): cmd_jobs_list,
        ("jobs", "submit"): cmd_jobs_submit,
        ("jobs", "status"): cmd_jobs_status,
        ("jobs", "result"): cmd_jobs_result,
        ("jobs", "cancel"): cmd_jobs_cancel,
        ("backends", "list"): cmd_backends_list,
        ("templates", "list"): cmd_templates_list,
        ("alerts", "list"): cmd_alerts_list,
        ("keys", "generate"): cmd_keys_generate,
        ("config", "set"): cmd_config_set,
        ("config", "get"): cmd_config_get,
        ("status",): cmd_status,
    }

    handler = commands.get(args.command)
    if handler:
        return await handler(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="qsop",
        description="Quantum-Safe Optimization Platform CLI",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Auth commands
    auth_parser = subparsers.add_parser("auth", help="Authentication commands")
    auth_subparsers = auth_parser.add_subparsers(dest="subcommand")

    login_parser = auth_subparsers.add_parser("login", help="Login to platform")
    login_parser.add_argument("--username", "-u", help="Username")
    login_parser.add_argument("--password", "-p", help="Password")

    auth_subparsers.add_parser("logout", help="Logout from platform")

    # Jobs commands
    jobs_parser = subparsers.add_parser("jobs", help="Job management")
    jobs_subparsers = jobs_parser.add_subparsers(dest="subcommand")

    jobs_list = jobs_subparsers.add_parser("list", help="List jobs")
    jobs_list.add_argument("--limit", "-l", type=int, default=20)

    jobs_submit = jobs_subparsers.add_parser("submit", help="Submit a job")
    jobs_submit.add_argument("config", help="Job configuration file (JSON)")

    jobs_status = jobs_subparsers.add_parser("status", help="Get job status")
    jobs_status.add_argument("job_id", help="Job ID")

    jobs_result = jobs_subparsers.add_parser("result", help="Get job result")
    jobs_result.add_argument("job_id", help="Job ID")
    jobs_result.add_argument("--output", "-o", help="Output file")

    jobs_cancel = jobs_subparsers.add_parser("cancel", help="Cancel a job")
    jobs_cancel.add_argument("job_id", help="Job ID")

    # Backends commands
    backends_parser = subparsers.add_parser("backends", help="Backend management")
    backends_subparsers = backends_parser.add_subparsers(dest="subcommand")
    backends_subparsers.add_parser("list", help="List backends")

    # Templates commands
    templates_parser = subparsers.add_parser("templates", help="Job templates")
    templates_subparsers = templates_parser.add_subparsers(dest="subcommand")
    templates_list = templates_subparsers.add_parser("list", help="List templates")
    templates_list.add_argument("--limit", "-l", type=int, default=20)

    # Alerts commands
    alerts_parser = subparsers.add_parser("alerts", help="Alert management")
    alerts_subparsers = alerts_parser.add_subparsers(dest="subcommand")
    alerts_subparsers.add_parser("list", help="List active alerts")

    # Keys commands
    keys_parser = subparsers.add_parser("keys", help="Key management")
    keys_subparsers = keys_parser.add_subparsers(dest="subcommand")
    keys_generate = keys_subparsers.add_parser("generate", help="Generate PQC key pair")
    keys_generate.add_argument("--save", "-s", help="Save keys to file")

    # Config commands
    config_parser = subparsers.add_parser("config", help="Configuration")
    config_subparsers = config_parser.add_subparsers(dest="subcommand")
    config_set = config_subparsers.add_parser("set", help="Set configuration")
    config_set.add_argument("key", help="Configuration key")
    config_set.add_argument("value", help="Configuration value")
    config_get = config_subparsers.add_parser("get", help="Get configuration")
    config_get.add_argument("key", help="Configuration key")

    # Status command
    subparsers.add_parser("status", help="Show platform status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
