"""OpenAPI Client Generator for QSOP.

Auto-generates Python and TypeScript client libraries from the OpenAPI spec.
Run as part of the release process:
    python scripts/generate_clients.py [--lang python|typescript --output-dir ./clients]
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def fetch_openapi_spec(base_url: str = "http://localhost:8000") -> dict:
    """Fetch OpenAPI spec from running server or generate it."""
    spec_path = Path(__file__).parent.parent / "api" / "openapi.json"

    # Try to fetch from running server first
    import urllib.request

    try:
        url = f"{base_url}/openapi.json"
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read())
    except Exception:
        pass

    # Try to generate from FastAPI app
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from api.main import app

        return app.openapi()
    except Exception as e:
        print(f"Warning: Could not generate OpenAPI spec: {e}")
        return {}


def generate_python_client(spec: dict, output_dir: Path):
    """Generate Python client using openapi-python-client."""
    spec_file = output_dir / "openapi.json"
    spec_file.write_text(json.dumps(spec, indent=2))

    print("Generating Python client...")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "openapi_python_client",
                "generate",
                "--path",
                str(spec_file),
                "--output-path",
                str(output_dir / "python-client"),
                "--meta",
                "setup",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print(f"Python client generated at: {output_dir / 'python-client'}")
        else:
            print(f"Python client generation failed: {result.stderr}")
    except FileNotFoundError:
        print("openapi-python-client not installed. Install with: pip install openapi-python-client")
    except subprocess.TimeoutExpired:
        print("Python client generation timed out")


def generate_typescript_client(spec: dict, output_dir: Path):
    """Generate TypeScript client using openapi-typescript-codegen."""
    spec_file = output_dir / "openapi.json"
    spec_file.write_text(json.dumps(spec, indent=2))

    ts_dir = output_dir / "typescript-client"
    ts_dir.mkdir(exist_ok=True)

    print("Generating TypeScript client...")

    # Generate using openapi-typescript-codegen (requires Node.js)
    try:
        result = subprocess.run(
            [
                "npx",
                "openapi-typescript-codegen",
                "--input",
                str(spec_file),
                "--output",
                str(ts_dir),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print(f"TypeScript client generated at: {ts_dir}")
        else:
            print(f"TypeScript client generation failed: {result.stderr}")
    except FileNotFoundError:
        print("npx not found. Install Node.js and npm to generate TypeScript client.")
    except subprocess.TimeoutExpired:
        print("TypeScript client generation timed out")


def generate_simple_python_client(spec: dict, output_dir: Path):
    """Generate a simple Python client without external dependencies.

    Creates a minimal client class with methods for each API endpoint.
    """
    client_dir = output_dir / "qsop-client"
    client_dir.mkdir(exist_ok=True)

    # Generate client code
    client_code = '''"""QSOP API Client - Auto-generated.

Usage:
    from qsop_client import QSOPClient

    client = QSOPClient(base_url="http://localhost:8000")
    client.login(username="user", password="pass")
    jobs = client.list_jobs()
'''

    # Extract paths from spec
    paths = spec.get("paths", {})

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                operation_id = operation.get("operationId", f"{method}_{path.strip('/').replace('/', '_')}")
                summary = operation.get("summary", "")
                client_code += f'''
    def {operation_id}(self, **kwargs):
        """{summary}"""
        return self._request("{method.upper()}", "{path}", **kwargs)
'''

    (client_dir / "client.py").write_text(client_code)
    (client_dir / "__init__.py").write_text("from .client import QSOPClient\n")

    print(f"Simple Python client generated at: {client_dir}")


def main():
    parser = argparse.ArgumentParser(description="Generate API clients from OpenAPI spec")
    parser.add_argument(
        "--lang",
        choices=["python", "typescript", "all"],
        default="all",
        help="Language to generate client for",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "clients",
        help="Output directory for generated clients",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of running QSOP server",
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Generate simple Python client without external dependencies",
    )

    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch OpenAPI spec
    spec = fetch_openapi_spec(args.base_url)
    if not spec:
        print("Error: Could not fetch OpenAPI spec. Is the server running?")
        sys.exit(1)

    # Save spec
    spec_file = args.output_dir / "openapi.json"
    spec_file.write_text(json.dumps(spec, indent=2))
    print(f"OpenAPI spec saved to: {spec_file}")

    # Generate clients
    if args.lang in ("python", "all"):
        if args.simple:
            generate_simple_python_client(spec, args.output_dir)
        else:
            generate_python_client(spec, args.output_dir)

    if args.lang in ("typescript", "all"):
        generate_typescript_client(spec, args.output_dir)

    print("Client generation complete!")


if __name__ == "__main__":
    main()
