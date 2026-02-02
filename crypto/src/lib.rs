//! Quantum-Safe Cryptography Module
//! 
//! Provides post-quantum cryptographic primitives based on NIST standards:
//! - ML-KEM-768 (FIPS 203) for key encapsulation
//! - ML-DSA-65 (FIPS 204) for digital signatures
//! - Hybrid encryption using ML-KEM + AES-256-GCM

pub mod error;
pub mod kem;
pub mod signatures;
pub mod encryption;

pub use error::CryptoError;
pub use kem::{KemKeyPair, EncapsulationResult, encapsulate, decapsulate};
pub use signatures::{SigningKeyPair, Signature, sign, verify};
pub use encryption::{EncryptedEnvelope, SignedEncryptedEnvelope, encrypt, decrypt};

use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use pyo3::types::PyModule;

/// Python bindings for quantum-safe cryptography
#[pymodule]
fn quantum_safe_crypto(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyKemKeyPair>()?;
    m.add_class::<PySigningKeyPair>()?;
    m.add_class::<PyEncryptedEnvelope>()?;
    m.add_class::<PySecurityLevel>()?;
    m.add_function(wrap_pyfunction!(py_kem_generate, m)?)?;
    m.add_function(wrap_pyfunction!(py_kem_generate_with_level, m)?)?;
    m.add_function(wrap_pyfunction!(py_kem_encapsulate, m)?)?;
    m.add_function(wrap_pyfunction!(py_kem_encapsulate_with_level, m)?)?;
    m.add_function(wrap_pyfunction!(py_kem_decapsulate, m)?)?;
    m.add_function(wrap_pyfunction!(py_kem_decapsulate_with_level, m)?)?;
    m.add_function(wrap_pyfunction!(py_sign, m)?)?;
    m.add_function(wrap_pyfunction!(py_sign_with_level, m)?)?;
    m.add_function(wrap_pyfunction!(py_verify, m)?)?;
    m.add_function(wrap_pyfunction!(py_verify_with_level, m)?)?;
    m.add_function(wrap_pyfunction!(py_encrypt, m)?)?;
    m.add_function(wrap_pyfunction!(py_decrypt, m)?)?;
    m.add_function(wrap_pyfunction!(py_get_supported_levels, m)?)?;
    Ok(())
}

/// Security level enum for Python
#[pyclass(name = "SecurityLevel")]
#[derive(Clone)]
pub struct PySecurityLevel {
    level: u8,
}

#[pymethods]
impl PySecurityLevel {
    #[new]
    fn new(level: u8) -> PyResult<Self> {
        match level {
            1 | 2 | 3 | 5 => Ok(PySecurityLevel { level }),
            _ => Err(PyValueError::new_err("Invalid security level. Use 1, 3, or 5")),
        }
    }
    
    #[getter]
    fn level(&self) -> u8 {
        self.level
    }
    
    #[getter]
    fn kem_algorithm(&self) -> &str {
        match self.level {
            1 => "ML-KEM-512",
            3 => "ML-KEM-768",
            5 => "ML-KEM-1024",
            _ => "ML-KEM-768",
        }
    }
    
    #[getter]
    fn dsa_algorithm(&self) -> &str {
        match self.level {
            1 | 2 => "ML-DSA-44",
            3 => "ML-DSA-65",
            5 => "ML-DSA-87",
            _ => "ML-DSA-65",
        }
    }
    
    #[staticmethod]
    fn level1() -> Self {
        PySecurityLevel { level: 1 }
    }
    
    #[staticmethod]
    fn level3() -> Self {
        PySecurityLevel { level: 3 }
    }
    
    #[staticmethod]
    fn level5() -> Self {
        PySecurityLevel { level: 5 }
    }
}

/// Python wrapper for KEM key pair
#[pyclass(name = "KemKeyPair")]
pub struct PyKemKeyPair {
    inner: KemKeyPair,
}

#[pymethods]
impl PyKemKeyPair {
    #[new]
    #[pyo3(signature = (security_level=None))]
    fn new(security_level: Option<u8>) -> PyResult<Self> {
        let level = match security_level.unwrap_or(3) {
            1 => kem::KemSecurityLevel::Level1,
            3 => kem::KemSecurityLevel::Level3,
            5 => kem::KemSecurityLevel::Level5,
            _ => return Err(PyValueError::new_err("Invalid security level. Use 1, 3, or 5")),
        };
        let inner = KemKeyPair::generate_with_level(level)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(PyKemKeyPair { inner })
    }

    #[getter]
    fn public_key(&self) -> String {
        self.inner.public_key_base64()
    }

    #[getter]
    fn secret_key(&self) -> String {
        self.inner.secret_key_base64()
    }
    
    #[getter]
    fn security_level(&self) -> u8 {
        match self.inner.security_level {
            kem::KemSecurityLevel::Level1 => 1,
            kem::KemSecurityLevel::Level3 => 3,
            kem::KemSecurityLevel::Level5 => 5,
        }
    }
    
    #[getter]
    fn algorithm(&self) -> &str {
        self.inner.security_level.algorithm_name()
    }

    #[staticmethod]
    fn from_base64(public_key: &str, secret_key: &str) -> PyResult<Self> {
        let inner = KemKeyPair::from_base64(public_key, secret_key)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(PyKemKeyPair { inner })
    }
}

/// Python wrapper for signing key pair
#[pyclass(name = "SigningKeyPair")]
pub struct PySigningKeyPair {
    inner: SigningKeyPair,
}

#[pymethods]
impl PySigningKeyPair {
    #[new]
    #[pyo3(signature = (security_level=None))]
    fn new(security_level: Option<u8>) -> PyResult<Self> {
        let level = match security_level.unwrap_or(3) {
            1 | 2 => signatures::SignatureSecurityLevel::Level2,
            3 => signatures::SignatureSecurityLevel::Level3,
            5 => signatures::SignatureSecurityLevel::Level5,
            _ => return Err(PyValueError::new_err("Invalid security level. Use 1, 3, or 5")),
        };
        let inner = SigningKeyPair::generate_with_level(level)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(PySigningKeyPair { inner })
    }

    #[getter]
    fn public_key(&self) -> String {
        self.inner.public_key_base64()
    }

    #[getter]
    fn secret_key(&self) -> String {
        self.inner.secret_key_base64()
    }
    
    #[getter]
    fn security_level(&self) -> u8 {
        match self.inner.security_level {
            signatures::SignatureSecurityLevel::Level2 => 2,
            signatures::SignatureSecurityLevel::Level3 => 3,
            signatures::SignatureSecurityLevel::Level5 => 5,
        }
    }
    
    #[getter]
    fn algorithm(&self) -> &str {
        self.inner.security_level.algorithm_name()
    }

    fn sign(&self, message: &[u8]) -> PyResult<String> {
        let signature = self.inner.sign(message)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &signature))
    }

    fn verify(&self, message: &[u8], signature: &str) -> PyResult<bool> {
        use base64::Engine;
        let sig_bytes = base64::engine::general_purpose::STANDARD
            .decode(signature)
            .map_err(|_| PyValueError::new_err("Invalid signature encoding"))?;
        self.inner.verify(message, &sig_bytes)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[staticmethod]
    fn from_base64(public_key: &str, secret_key: &str) -> PyResult<Self> {
        let inner = SigningKeyPair::from_base64(public_key, secret_key)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(PySigningKeyPair { inner })
    }
}

/// Python wrapper for encrypted envelope
#[pyclass(name = "EncryptedEnvelope")]
pub struct PyEncryptedEnvelope {
    inner: EncryptedEnvelope,
}

#[pymethods]
impl PyEncryptedEnvelope {
    fn to_json(&self) -> PyResult<String> {
        self.inner.to_base64_json()
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    #[staticmethod]
    fn from_json(json: &str) -> PyResult<Self> {
        let inner = EncryptedEnvelope::from_base64_json(json)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(PyEncryptedEnvelope { inner })
    }
}

/// Generate a new KEM key pair
#[pyfunction]
fn py_kem_generate() -> PyResult<PyKemKeyPair> {
    PyKemKeyPair::new(None)
}

/// Generate a new KEM key pair with specified security level
#[pyfunction]
fn py_kem_generate_with_level(security_level: u8) -> PyResult<PyKemKeyPair> {
    PyKemKeyPair::new(Some(security_level))
}

/// Encapsulate a shared secret (default Level 3)
#[pyfunction]
fn py_kem_encapsulate(public_key: &str) -> PyResult<(String, String)> {
    let result = kem::encapsulate_base64(public_key)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((
        result.ciphertext_base64(),
        base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &result.shared_secret),
    ))
}

/// Encapsulate with specified security level
#[pyfunction]
fn py_kem_encapsulate_with_level(public_key: &str, security_level: u8) -> PyResult<(String, String)> {
    use base64::Engine;
    let level = match security_level {
        1 => kem::KemSecurityLevel::Level1,
        3 => kem::KemSecurityLevel::Level3,
        5 => kem::KemSecurityLevel::Level5,
        _ => return Err(PyValueError::new_err("Invalid security level. Use 1, 3, or 5")),
    };
    let public_key_bytes = base64::engine::general_purpose::STANDARD
        .decode(public_key)
        .map_err(|_| PyValueError::new_err("Invalid public key encoding"))?;
    let result = kem::encapsulate_with_level(&public_key_bytes, level)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((
        result.ciphertext_base64(),
        base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &result.shared_secret),
    ))
}

/// Decapsulate to recover shared secret (default Level 3)
#[pyfunction]
fn py_kem_decapsulate(ciphertext: &str, secret_key: &str) -> PyResult<String> {
    let shared_secret = kem::decapsulate_base64(ciphertext, secret_key)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &shared_secret))
}

/// Decapsulate with specified security level
#[pyfunction]
fn py_kem_decapsulate_with_level(ciphertext: &str, secret_key: &str, security_level: u8) -> PyResult<String> {
    use base64::Engine;
    let level = match security_level {
        1 => kem::KemSecurityLevel::Level1,
        3 => kem::KemSecurityLevel::Level3,
        5 => kem::KemSecurityLevel::Level5,
        _ => return Err(PyValueError::new_err("Invalid security level. Use 1, 3, or 5")),
    };
    let ciphertext_bytes = base64::engine::general_purpose::STANDARD
        .decode(ciphertext)
        .map_err(|_| PyValueError::new_err("Invalid ciphertext encoding"))?;
    let secret_key_bytes = base64::engine::general_purpose::STANDARD
        .decode(secret_key)
        .map_err(|_| PyValueError::new_err("Invalid secret key encoding"))?;
    let shared_secret = kem::decapsulate_with_level(&ciphertext_bytes, &secret_key_bytes, level)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &shared_secret))
}

/// Sign a message (default Level 3)
#[pyfunction]
fn py_sign(message: &[u8], secret_key: &str) -> PyResult<String> {
    let signature = signatures::sign_base64(message, secret_key)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(signature.to_base64())
}

/// Sign with specified security level
#[pyfunction]
fn py_sign_with_level(message: &[u8], secret_key: &str, security_level: u8) -> PyResult<String> {
    use base64::Engine;
    let level = match security_level {
        1 | 2 => signatures::SignatureSecurityLevel::Level2,
        3 => signatures::SignatureSecurityLevel::Level3,
        5 => signatures::SignatureSecurityLevel::Level5,
        _ => return Err(PyValueError::new_err("Invalid security level. Use 1, 3, or 5")),
    };
    let secret_key_bytes = base64::engine::general_purpose::STANDARD
        .decode(secret_key)
        .map_err(|_| PyValueError::new_err("Invalid secret key encoding"))?;
    let signature = signatures::sign_with_level(message, &secret_key_bytes, level)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &signature))
}

/// Verify a signature (default Level 3)
#[pyfunction]
fn py_verify(message: &[u8], signature: &str, public_key: &str) -> PyResult<bool> {
    signatures::verify_base64(message, signature, public_key)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Verify with specified security level
#[pyfunction]
fn py_verify_with_level(message: &[u8], signature: &str, public_key: &str, security_level: u8) -> PyResult<bool> {
    use base64::Engine;
    let level = match security_level {
        1 | 2 => signatures::SignatureSecurityLevel::Level2,
        3 => signatures::SignatureSecurityLevel::Level3,
        5 => signatures::SignatureSecurityLevel::Level5,
        _ => return Err(PyValueError::new_err("Invalid security level. Use 1, 3, or 5")),
    };
    let signature_bytes = base64::engine::general_purpose::STANDARD
        .decode(signature)
        .map_err(|_| PyValueError::new_err("Invalid signature encoding"))?;
    let public_key_bytes = base64::engine::general_purpose::STANDARD
        .decode(public_key)
        .map_err(|_| PyValueError::new_err("Invalid public key encoding"))?;
    signatures::verify_with_level(message, &signature_bytes, &public_key_bytes, level)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Get supported security levels and their algorithms
#[pyfunction]
fn py_get_supported_levels() -> PyResult<Vec<(u8, String, String)>> {
    Ok(vec![
        (1, "ML-KEM-512".to_string(), "ML-DSA-44".to_string()),
        (3, "ML-KEM-768".to_string(), "ML-DSA-65".to_string()),
        (5, "ML-KEM-1024".to_string(), "ML-DSA-87".to_string()),
    ])
}

/// Encrypt data
#[pyfunction]
fn py_encrypt(plaintext: &[u8], recipient_public_key: &str) -> PyResult<PyEncryptedEnvelope> {
    let inner = encryption::encrypt_base64(plaintext, recipient_public_key)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok(PyEncryptedEnvelope { inner })
}

/// Decrypt data
#[pyfunction]
fn py_decrypt(envelope: &PyEncryptedEnvelope, recipient_secret_key: &str) -> PyResult<Vec<u8>> {
    encryption::decrypt_base64(&envelope.inner, recipient_secret_key)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}
