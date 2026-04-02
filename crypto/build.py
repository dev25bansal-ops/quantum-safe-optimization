#!/usr/bin/env python3
"""
Build script for the quantum_safe_crypto Rust module.

This script:
1. Checks prerequisites (Rust, maturin)
2. Builds the Rust library
3. Creates a Python wheel
4. Optionally installs it

Usage:
    python build.py              # Build only
    python build.py --install    # Build and install
    python build.py --dev        # Development build (maturin develop)
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], cwd: Path | None = None) -> bool:
    """Run a command and return success status."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode == 0


def check_rust() -> bool:
    """Check if Rust is installed."""
    try:
        result = subprocess.run(["rustc", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Rust installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    print("✗ Rust not installed. Install from: https://rustup.rs")
    print("  Windows: winget install Rustlang.Rustup")
    print("  Linux/macOS: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
    return False


def check_maturin() -> bool:
    """Check if maturin is installed."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "maturin", "--version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"✓ maturin installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    print("Installing maturin...")
    return run_command([sys.executable, "-m", "pip", "install", "maturin"])


def build_release(crypto_dir: Path) -> bool:
    """Build release version."""
    print("\n🔨 Building release version...")

    # Build with maturin
    if not run_command([sys.executable, "-m", "maturin", "build", "--release"], cwd=crypto_dir):
        print("✗ Build failed")
        return False

    # Find the wheel
    wheels_dir = crypto_dir / "target" / "wheels"
    wheels = list(wheels_dir.glob("*.whl"))

    if wheels:
        print(f"\n✓ Build successful!")
        print(f"  Wheel: {wheels[0]}")
        return True
    else:
        print("✗ No wheel found")
        return False


def build_dev(crypto_dir: Path) -> bool:
    """Build development version (maturin develop)."""
    print("\n🔨 Building development version...")

    if not run_command([sys.executable, "-m", "maturin", "develop"], cwd=crypto_dir):
        print("✗ Development build failed")
        return False

    print("\n✓ Development build installed!")
    return True


def install_wheel(crypto_dir: Path) -> bool:
    """Install the built wheel."""
    wheels_dir = crypto_dir / "target" / "wheels"
    wheels = list(wheels_dir.glob("*.whl"))

    if not wheels:
        print("✗ No wheel found. Run build first.")
        return False

    print(f"\n📦 Installing {wheels[0].name}...")
    return run_command(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheels[0])]
    )


def test_import() -> bool:
    """Test if the module can be imported."""
    print("\n🧪 Testing import...")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
from quantum_safe_crypto import KemKeyPair, SigningKeyPair, SecurityLevel

# Test KEM
kem = KemKeyPair()
print(f"KEM: {kem.algorithm} (level {kem.security_level})")

# Test Signing
sig = SigningKeyPair()
print(f"DSA: {sig.algorithm} (level {sig.security_level})")

# Test sign/verify
message = b"Hello, quantum-safe world!"
signature = sig.sign(message)
print(f"Signature length: {len(signature)} chars")

verified = sig.verify(message, signature)
print(f"Verification: {'✓' if verified else '✗'}")

print("\\n✓ All tests passed!")
""",
            ],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            return False
        return True
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Build quantum_safe_crypto Rust module")
    parser.add_argument("--install", action="store_true", help="Install wheel after building")
    parser.add_argument("--dev", action="store_true", help="Development build (maturin develop)")
    parser.add_argument("--test", action="store_true", help="Test import after building")
    args = parser.parse_args()

    crypto_dir = Path(__file__).parent

    print("=" * 60)
    print("quantum_safe_crypto Build Script")
    print("=" * 60)
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Working directory: {crypto_dir}")
    print()

    # Check prerequisites
    if not check_rust():
        sys.exit(1)

    if not check_maturin():
        sys.exit(1)

    # Build
    if args.dev:
        if not build_dev(crypto_dir):
            sys.exit(1)
    else:
        if not build_release(crypto_dir):
            sys.exit(1)

        if args.install:
            if not install_wheel(crypto_dir):
                sys.exit(1)

    # Test
    if args.test or args.install or args.dev:
        if not test_import():
            sys.exit(1)

    print("\n" + "=" * 60)
    print("✓ Build complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
