"""
Jupyter Notebook Integration for QSOP.

Provides:
- Custom Jupyter kernel for quantum optimization
- Magic commands for job submission
- Rich display of quantum circuits and results
"""

import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field


class QSOPMagic:
    """Base class for QSOP magic commands."""

    name: str = ""
    help_text: str = ""

    def execute(self, line: str, cell: str | None = None) -> Any:
        """Execute the magic command."""
        raise NotImplementedError


class QSOPClient:
    """Client for QSOP API from Jupyter notebooks."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._tenant_id: str | None = None

    def login(self, username: str, password: str) -> dict:
        """Login and store token."""
        import httpx

        response = httpx.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        response.raise_for_status()
        data = response.json()
        self._token = data.get("access_token")
        return data

    def set_tenant(self, tenant_id: str) -> None:
        """Set current tenant context."""
        self._tenant_id = tenant_id

    def _headers(self) -> dict[str, str]:
        """Get authorization headers."""
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def submit_job(
        self,
        algorithm: str,
        problem_config: dict,
        parameters: dict | None = None,
    ) -> dict:
        """Submit an optimization job."""
        import httpx

        payload = {
            "algorithm": algorithm,
            "problem_config": problem_config,
        }
        if parameters:
            payload["parameters"] = parameters

        response = httpx.post(
            f"{self.base_url}/api/v1/jobs",
            json=payload,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_job(self, job_id: str) -> dict:
        """Get job status."""
        import httpx

        response = httpx.get(
            f"{self.base_url}/api/v1/jobs/{job_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def wait_for_job(self, job_id: str, timeout: float = 300, poll_interval: float = 2.0) -> dict:
        """Wait for job completion."""
        import time

        start = time.time()
        while time.time() - start < timeout:
            job = self.get_job(job_id)
            if job.get("status") in ("completed", "failed", "cancelled"):
                return job
            time.sleep(poll_interval)

        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

    def get_circuit(self, job_id: str) -> dict:
        """Get circuit visualization data."""
        import httpx

        response = httpx.get(
            f"{self.base_url}/api/v1/jobs/{job_id}/circuit",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()


# Global client instance for notebook
_client: QSOPClient | None = None


def get_client() -> QSOPClient:
    """Get or create the global QSOP client."""
    global _client
    if _client is None:
        _client = QSOPClient()
    return _client


# Magic Commands


def qaoa(line: str) -> dict:
    """
    Submit a QAOA job.

    Usage:
        %qaoa --edges [[0,1],[1,2],[2,0]] --layers 2 --shots 1024

    Parameters:
        --edges: Graph edges as JSON
        --layers: Number of QAOA layers (default: 2)
        --shots: Number of shots (default: 1024)
        --optimizer: Classical optimizer (default: COBYLA)
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--edges", type=str, required=True)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--optimizer", type=str, default="COBYLA")

    args = parser.parse_args(line.split())

    edges = json.loads(args.edges)

    client = get_client()
    job = client.submit_job(
        algorithm="QAOA",
        problem_config={
            "type": "maxcut",
            "graph": {"edges": edges},
        },
        parameters={
            "layers": args.layers,
            "shots": args.shots,
            "optimizer": args.optimizer,
        },
    )

    print(f"Submitted job: {job['id']}")
    return job


def vqe(line: str) -> dict:
    """
    Submit a VQE job.

    Usage:
        %vqe --molecule H2 --shots 1024

    Parameters:
        --molecule: Molecule name (H2, LiH, H2O, etc.)
        --ansatz: Ansatz type (default: hardware_efficient)
        --shots: Number of shots (default: 1024)
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--molecule", type=str, default="H2")
    parser.add_argument("--ansatz", type=str, default="hardware_efficient")
    parser.add_argument("--shots", type=int, default=1024)

    args = parser.parse_args(line.split())

    client = get_client()
    job = client.submit_job(
        algorithm="VQE",
        problem_config={
            "type": "molecular_hamiltonian",
            "molecule": args.molecule,
        },
        parameters={
            "ansatz_type": args.ansatz,
            "shots": args.shots,
        },
    )

    print(f"Submitted job: {job['id']}")
    return job


def anneal(line: str) -> dict:
    """
    Submit a quantum annealing job.

    Usage:
        %anneal --matrix [[0,1,-1],[1,2,2]] --reads 100

    Parameters:
        --matrix: QUBO matrix as JSON
        --reads: Number of reads (default: 100)
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=str, required=True)
    parser.add_argument("--reads", type=int, default=100)

    args = parser.parse_args(line.split())

    matrix = json.loads(args.matrix)

    client = get_client()
    job = client.submit_job(
        algorithm="ANNEALING",
        problem_config={
            "type": "qubo",
            "qubo_matrix": matrix,
        },
        parameters={
            "reads": args.reads,
        },
    )

    print(f"Submitted job: {job['id']}")
    return job


def connect(line: str) -> None:
    """
    Connect to QSOP API.

    Usage:
        %connect --url http://localhost:8000 --user admin --password changeme
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, default="http://localhost:8000")
    parser.add_argument("--user", type=str, required=True)
    parser.add_argument("--password", type=str, required=True)

    args = parser.parse_args(line.split())

    client = get_client()
    client.base_url = args.url
    result = client.login(args.user, args.password)

    print(f"Connected to {args.url}")
    print(f"Logged in as: {args.user}")


def wait(line: str) -> dict:
    """
    Wait for a job to complete.

    Usage:
        %wait --job-id <id> --timeout 300

    Parameters:
        --job-id: Job ID to wait for
        --timeout: Timeout in seconds (default: 300)
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=str, required=True)
    parser.add_argument("--timeout", type=float, default=300)

    args = parser.parse_args(line.split())

    client = get_client()
    job = client.wait_for_job(args.job_id, timeout=args.timeout)

    print(f"Job {args.job_id} finished with status: {job['status']}")
    if job.get("result"):
        print(f"Result: {job['result']}")

    return job


def circuit(line: str) -> None:
    """
    Display circuit visualization.

    Usage:
        %circuit --job-id <id>

    This will render an interactive circuit diagram in the notebook.
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=str, required=True)

    args = parser.parse_args(line.split())

    client = get_client()
    circuit_data = client.get_circuit(args.job_id)

    # Return circuit data for rendering
    return display_circuit(circuit_data)


def display_circuit(circuit_data: dict) -> dict:
    """Display circuit using IPython display system."""
    try:
        from IPython.display import HTML, display

        # Generate SVG from circuit data
        svg = generate_circuit_svg(circuit_data)
        display(HTML(svg))

    except ImportError:
        print("Circuit display requires IPython/Jupyter")
        print(
            f"Circuit: {circuit_data.get('depth', 0)} layers, {circuit_data.get('qubit_count', 0)} qubits"
        )

    return circuit_data


def generate_circuit_svg(circuit_data: dict) -> str:
    """Generate SVG visualization of a quantum circuit."""
    depth = circuit_data.get("depth", 10)
    qubits = circuit_data.get("qubit_count", 5)
    gate_counts = circuit_data.get("gate_counts", {})

    width = max(800, depth * 60)
    height = max(300, qubits * 50 + 100)

    svg_parts = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']

    # Background
    svg_parts.append(f'<rect width="100%" height="100%" fill="#1a1a2e"/>')

    # Title
    svg_parts.append(
        f'<text x="20" y="30" fill="#fff" font-family="monospace" font-size="14">Quantum Circuit - Depth: {depth}, Qubits: {qubits}</text>'
    )

    # Quantum wires
    for q in range(qubits):
        y = 60 + q * 50
        svg_parts.append(
            f'<line x1="50" y1="{y}" x2="{width - 50}" y2="{y}" stroke="#4a4a6a" stroke-width="2"/>'
        )
        svg_parts.append(
            f'<text x="20" y="{y + 5}" fill="#888" font-family="monospace" font-size="12">q{q}</text>'
        )

    # Gate placeholders (simplified)
    gate_x = 100
    for gate_type, count in gate_counts.items():
        color = {
            "h": "#6366f1",
            "x": "#ef4444",
            "cx": "#22c55e",
            "rz": "#f59e0b",
            "ry": "#8b5cf6",
        }.get(gate_type.lower(), "#666")

        svg_parts.append(
            f'<rect x="{gate_x}" y="50" width="40" height="{qubits * 50}" fill="{color}" opacity="0.3" rx="5"/>'
        )
        svg_parts.append(
            f'<text x="{gate_x + 5}" y="{height - 30}" fill="{color}" font-family="monospace" font-size="12">{gate_type}: {count}</text>'
        )
        gate_x += 60

    svg_parts.append("</svg>")

    return "".join(svg_parts)


# Cell magic for multi-line job definition
def qsop_job(cell: str) -> dict:
    """
    Cell magic for defining and submitting a job.

    Usage:
        %%qsop_job

        algorithm: QAOA
        layers: 2
        shots: 1024

        problem:
          type: maxcut
          edges:
            - [0, 1]
            - [1, 2]
            - [2, 0]
    """
    import yaml

    config = yaml.safe_load(cell)

    algorithm = config.pop("algorithm", "QAOA")
    problem_config = config.pop("problem", {})

    client = get_client()
    job = client.submit_job(algorithm, problem_config, config)

    print(f"Submitted {algorithm} job: {job['id']}")
    return job


# Register magics
MAGICS: dict[str, Callable] = {
    "connect": connect,
    "qaoa": qaoa,
    "vqe": vqe,
    "anneal": anneal,
    "wait": wait,
    "circuit": circuit,
}

CELL_MAGICS: dict[str, Callable] = {
    "qsop_job": qsop_job,
}


def load_ipython_extension(ipython):
    """Load the QSOP extension in IPython/Jupyter."""
    from IPython.core.magic import register_line_magic, register_cell_magic

    # Register line magics
    for name, func in MAGICS.items():
        ipython.register_magic_function(func, "line", name)

    # Register cell magics
    for name, func in CELL_MAGICS.items():
        ipython.register_magic_function(func, "cell", name)

    print("QSOP extension loaded. Available magics:")
    print("  Line magics: %connect, %qaoa, %vqe, %anneal, %wait, %circuit")
    print("  Cell magics: %%qsop_job")
    print("\nQuick start:")
    print("  %connect --user admin --password changeme")
    print("  %qaoa --edges '[[0,1],[1,2],[2,0]]' --layers 2")
