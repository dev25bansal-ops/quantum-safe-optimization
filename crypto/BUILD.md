# Building the Rust Crypto Module

The Rust crypto module provides real post-quantum cryptography using ML-KEM (Kyber) and ML-DSA (Dilithium).

## Prerequisites

### Windows

1. Install Visual Studio Build Tools:

   ```powershell
   winget install Microsoft.VisualStudio.2022.BuildTools
   ```

   Or download from: https://visualstudio.microsoft.com/downloads/

   Select "Desktop development with C++" workload.

2. Install Rust:

   ```powershell
   winget install Rustlang.Rustup
   ```

3. Install maturin:
   ```powershell
   pip install maturin
   ```

### Linux

```bash
# Ubuntu/Debian
sudo apt install build-essential libssl-dev pkg-config
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
pip install maturin
```

### macOS

```bash
xcode-select --install
brew install rustup
rustup-init
pip install maturin
```

## Building

```bash
cd crypto
cargo build --release
maturin build --release
```

## Installing the Wheel

```bash
pip install target/wheels/quantum_safe_crypto-*.whl
```

## Development Build

```bash
maturin develop
```

## Testing

```bash
cargo test
python -c "from quantum_safe_crypto import KemKeyPair; kp = KemKeyPair(); print(kp.algorithm)"
```

## Fallback

If the Rust module is not available, the Python fallback (`quantum_safe_crypto.py`) will be used.
This fallback is suitable for development but NOT for production use.

## Security Levels

| Level | KEM Algorithm | Signature Algorithm | Key Size   |
| ----- | ------------- | ------------------- | ---------- |
| 1     | ML-KEM-512    | ML-DSA-44           | 800 bytes  |
| 3     | ML-KEM-768    | ML-DSA-65           | 1184 bytes |
| 5     | ML-KEM-1024   | ML-DSA-87           | 1568 bytes |

## Dependencies

- pqcrypto-kyber: ML-KEM implementation
- pqcrypto-dilithium: ML-DSA implementation
- aes-gcm: Symmetric encryption
- pyo3: Python bindings
