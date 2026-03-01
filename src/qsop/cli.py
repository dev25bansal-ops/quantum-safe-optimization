"""
Command-line interface for the quantum-safe optimization platform.

Provides commands for running optimization jobs, managing keys, and administration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="qsop",
        description="Quantum-Safe Secure Optimization Platform",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start the API server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")  # noqa: S104 - Accepting connections from all interfaces
    server_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    server_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # Optimize command
    opt_parser = subparsers.add_parser("optimize", help="Run an optimization job")
    opt_parser.add_argument("--problem", type=Path, required=True, help="Path to problem JSON file")
    opt_parser.add_argument("--algorithm", default="qaoa", help="Optimization algorithm")
    opt_parser.add_argument("--backend", default="statevector", help="Quantum backend")
    opt_parser.add_argument("--shots", type=int, default=1024, help="Number of shots")
    opt_parser.add_argument("--output", type=Path, help="Output file for results")

    # Keygen command
    key_parser = subparsers.add_parser("keygen", help="Generate cryptographic keys")
    key_parser.add_argument("--type", choices=["kem", "signature"], required=True, help="Key type")
    key_parser.add_argument(
        "--algorithm", help="Algorithm (default: Kyber768 for KEM, Dilithium3 for sig)"
    )
    key_parser.add_argument("--output", type=Path, help="Output directory for keys")

    # Encrypt command
    enc_parser = subparsers.add_parser("encrypt", help="Encrypt a file")
    enc_parser.add_argument("input", type=Path, help="Input file")
    enc_parser.add_argument("--key", type=Path, required=True, help="Public key file")
    enc_parser.add_argument("--output", type=Path, help="Output file")

    # Decrypt command
    dec_parser = subparsers.add_parser("decrypt", help="Decrypt a file")
    dec_parser.add_argument("input", type=Path, help="Input file")
    dec_parser.add_argument("--key", type=Path, required=True, help="Private key file")
    dec_parser.add_argument("--output", type=Path, help="Output file")

    # Info command
    subparsers.add_parser("info", help="Show system information")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "server":
        return cmd_server(args)
    elif args.command == "optimize":
        return cmd_optimize(args)
    elif args.command == "keygen":
        return cmd_keygen(args)
    elif args.command == "encrypt":
        return cmd_encrypt(args)
    elif args.command == "decrypt":
        return cmd_decrypt(args)
    elif args.command == "info":
        return cmd_info(args)

    return 1


def cmd_server(args: argparse.Namespace) -> int:
    """Start the API server."""
    try:
        import uvicorn

        from qsop.main import app

        uvicorn.run(
            "qsop.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return 0
    except ImportError:
        return 1


def cmd_optimize(args: argparse.Namespace) -> int:
    """Run an optimization job."""

    # Load problem
    try:
        with open(args.problem) as f:
            problem_data = json.load(f)
    except Exception:
        return 1

    # Create problem
    from qsop.domain.models.problem import OptimizationProblem, Variable, VariableType

    variables = [
        Variable(
            name=v.get("name", f"x_{i}"),
            var_type=VariableType(v.get("type", "continuous")),
            lower_bound=v.get("lower_bound", -10),
            upper_bound=v.get("upper_bound", 10),
        )
        for i, v in enumerate(problem_data.get("variables", []))
    ]

    # Simple objective for demo
    def objective(x):
        return sum(xi**2 for xi in x)

    problem = OptimizationProblem(
        variables=variables,
        objective=objective,
        metadata=problem_data.get("metadata", {}),
    )

    # Get backend
    if args.backend == "statevector":
        from qsop.backends.simulators.statevector import StatevectorSimulator

        StatevectorSimulator()
    elif args.backend == "qiskit_aer":
        from qsop.backends.simulators.qiskit_aer import QiskitAerBackend

        QiskitAerBackend()
    else:
        return 1

    # Get optimizer
    if args.algorithm == "gradient_descent":
        from qsop.optimizers.classical.gradient_descent import GradientDescentOptimizer

        optimizer = GradientDescentOptimizer()
        result = optimizer.optimize(problem)
    elif args.algorithm == "genetic_algorithm":
        from qsop.optimizers.classical.evolutionary import GeneticAlgorithm

        optimizer = GeneticAlgorithm()
        result = optimizer.optimize(problem)
    else:
        from qsop.optimizers.classical.gradient_descent import GradientDescentOptimizer

        optimizer = GradientDescentOptimizer()
        result = optimizer.optimize(problem)

    # Output results
    result_dict = {
        "optimal_value": result.optimal_value,
        "optimal_parameters": result.optimal_parameters,
        "iterations": result.iterations,
        "converged": result.converged,
    }

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result_dict, f, indent=2)
    else:
        pass

    return 0


def cmd_keygen(args: argparse.Namespace) -> int:
    """Generate cryptographic keys."""
    from qsop.crypto.pqc import (
        KEMAlgorithm,
        SignatureAlgorithm,
        get_kem,
        get_signature_scheme,
    )

    output_dir = args.output or Path(".")
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.type == "kem":
        algorithm = KEMAlgorithm(args.algorithm) if args.algorithm else KEMAlgorithm.KYBER768

        kem = get_kem(algorithm)
        public_key, private_key = kem.keygen()

        pub_file = output_dir / f"{algorithm.value}_public.key"
        priv_file = output_dir / f"{algorithm.value}_private.key"

        pub_file.write_bytes(public_key)
        priv_file.write_bytes(private_key)

    else:  # signature
        algorithm = (
            SignatureAlgorithm(args.algorithm) if args.algorithm else SignatureAlgorithm.DILITHIUM3
        )

        sig = get_signature_scheme(algorithm)
        public_key, private_key = sig.keygen()

        pub_file = output_dir / f"{algorithm.value}_public.key"
        priv_file = output_dir / f"{algorithm.value}_private.key"

        pub_file.write_bytes(public_key)
        priv_file.write_bytes(private_key)

    return 0


def cmd_encrypt(args: argparse.Namespace) -> int:
    """Encrypt a file."""
    return 1


def cmd_decrypt(args: argparse.Namespace) -> int:
    """Decrypt a file."""
    return 1


def cmd_info(args: argparse.Namespace) -> int:
    """Show system information."""
    from qsop.crypto.pqc import KEMAlgorithm, SignatureAlgorithm, is_oqs_available

    # Check liboqs
    "Available" if is_oqs_available() else "Not installed"

    # Check Qiskit
    try:
        import qiskit
    except ImportError:
        pass

    # Check Qiskit Aer
    try:
        import qiskit_aer
    except ImportError:
        pass

    for _alg in KEMAlgorithm:
        pass

    for _alg in SignatureAlgorithm:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
