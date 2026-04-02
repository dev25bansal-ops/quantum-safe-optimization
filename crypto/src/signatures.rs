//! ML-DSA (CRYSTALS-Dilithium) Digital Signatures
//!
//! Implements NIST FIPS 204 ML-DSA for post-quantum secure digital signatures.
//! Supports all three security levels:
//! - ML-DSA-44 (Level 2) - Lightweight, suitable for constrained environments
//! - ML-DSA-65 (Level 3) - Recommended, balanced security/performance
//! - ML-DSA-87 (Level 5) - Maximum security

use crate::error::CryptoError;
use pqcrypto_dilithium::{dilithium2, dilithium3, dilithium5};
use pqcrypto_traits::sign::{DetachedSignature, PublicKey, SecretKey};
use serde::{Deserialize, Serialize};

/// Security level for ML-DSA
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SignatureSecurityLevel {
    /// ML-DSA-44 (NIST Level 2) - Lightweight
    Level2,
    /// ML-DSA-65 (NIST Level 3) - Recommended
    Level3,
    /// ML-DSA-87 (NIST Level 5) - Maximum security
    Level5,
}

impl Default for SignatureSecurityLevel {
    fn default() -> Self {
        SignatureSecurityLevel::Level3
    }
}

impl SignatureSecurityLevel {
    /// Get the algorithm name for this security level
    pub fn algorithm_name(&self) -> &'static str {
        match self {
            SignatureSecurityLevel::Level2 => "ML-DSA-44",
            SignatureSecurityLevel::Level3 => "ML-DSA-65",
            SignatureSecurityLevel::Level5 => "ML-DSA-87",
        }
    }

    /// Get key/signature sizes for this security level
    pub fn sizes(&self) -> (usize, usize, usize) {
        // Returns (public_key_size, secret_key_size, signature_size)
        match self {
            SignatureSecurityLevel::Level2 => (1312, 2560, 2420),
            SignatureSecurityLevel::Level3 => (1952, 4032, 3293),
            SignatureSecurityLevel::Level5 => (2592, 4896, 4595),
        }
    }

    /// Parse from string (e.g., "2", "3", "5" or "level2", "level3", "level5")
    pub fn from_str(s: &str) -> Result<Self, CryptoError> {
        match s.to_lowercase().trim() {
            "1" | "2" | "level1" | "level2" | "l2" | "44" => Ok(SignatureSecurityLevel::Level2),
            "3" | "level3" | "l3" | "65" => Ok(SignatureSecurityLevel::Level3),
            "5" | "level5" | "l5" | "87" => Ok(SignatureSecurityLevel::Level5),
            _ => Err(CryptoError::UnsupportedSecurityLevel),
        }
    }
}

/// ML-DSA signing key pair
#[derive(Clone)]
pub struct SigningKeyPair {
    pub public_key: Vec<u8>,
    pub secret_key: Vec<u8>,
    pub security_level: SignatureSecurityLevel,
}

impl SigningKeyPair {
    /// Generate a new ML-DSA-65 key pair (default Level 3)
    pub fn generate() -> Result<Self, CryptoError> {
        Self::generate_with_level(SignatureSecurityLevel::Level3)
    }

    /// Generate key pair with specified security level
    pub fn generate_with_level(level: SignatureSecurityLevel) -> Result<Self, CryptoError> {
        match level {
            SignatureSecurityLevel::Level2 => {
                let (pk, sk) = dilithium2::keypair();
                Ok(SigningKeyPair {
                    public_key: pk.as_bytes().to_vec(),
                    secret_key: sk.as_bytes().to_vec(),
                    security_level: level,
                })
            }
            SignatureSecurityLevel::Level3 => {
                let (pk, sk) = dilithium3::keypair();
                Ok(SigningKeyPair {
                    public_key: pk.as_bytes().to_vec(),
                    secret_key: sk.as_bytes().to_vec(),
                    security_level: level,
                })
            }
            SignatureSecurityLevel::Level5 => {
                let (pk, sk) = dilithium5::keypair();
                Ok(SigningKeyPair {
                    public_key: pk.as_bytes().to_vec(),
                    secret_key: sk.as_bytes().to_vec(),
                    security_level: level,
                })
            }
        }
    }

    /// Export public key as base64
    pub fn public_key_base64(&self) -> String {
        base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &self.public_key)
    }

    /// Export secret key as base64 (handle with care!)
    pub fn secret_key_base64(&self) -> String {
        base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &self.secret_key)
    }

    /// Import from base64 encoded keys
    pub fn from_base64(public_key_b64: &str, secret_key_b64: &str) -> Result<Self, CryptoError> {
        use base64::Engine;
        let public_key = base64::engine::general_purpose::STANDARD
            .decode(public_key_b64)
            .map_err(|_| CryptoError::InvalidKeyFormat)?;
        let secret_key = base64::engine::general_purpose::STANDARD
            .decode(secret_key_b64)
            .map_err(|_| CryptoError::InvalidKeyFormat)?;

        Ok(SigningKeyPair {
            public_key,
            secret_key,
            security_level: SignatureSecurityLevel::Level3,
        })
    }

    /// Sign a message
    pub fn sign(&self, message: &[u8]) -> Result<Vec<u8>, CryptoError> {
        sign_with_level(message, &self.secret_key, self.security_level)
    }

    /// Verify a signature
    pub fn verify(&self, message: &[u8], signature: &[u8]) -> Result<bool, CryptoError> {
        verify_with_level(message, signature, &self.public_key, self.security_level)
    }
}

/// Digital signature container
#[derive(Clone, Serialize, Deserialize)]
pub struct Signature {
    pub signature: Vec<u8>,
    pub algorithm: String,
}

impl Signature {
    /// Create from raw signature bytes
    pub fn new(signature: Vec<u8>) -> Self {
        Signature {
            signature,
            algorithm: "ML-DSA-65".to_string(),
        }
    }

    /// Export signature as base64
    pub fn to_base64(&self) -> String {
        base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &self.signature)
    }

    /// Import from base64
    pub fn from_base64(signature_b64: &str) -> Result<Self, CryptoError> {
        use base64::Engine;
        let signature = base64::engine::general_purpose::STANDARD
            .decode(signature_b64)
            .map_err(|_| CryptoError::InvalidSignature)?;
        Ok(Signature::new(signature))
    }
}

/// Sign a message using ML-DSA
///
/// # Arguments
/// * `message` - Message bytes to sign
/// * `secret_key` - Signer's secret key
///
/// # Returns
/// * Detached signature bytes
pub fn sign(message: &[u8], secret_key: &[u8]) -> Result<Vec<u8>, CryptoError> {
    sign_with_level(message, secret_key, SignatureSecurityLevel::Level3)
}

/// Sign with explicit security level
pub fn sign_with_level(
    message: &[u8],
    secret_key: &[u8],
    level: SignatureSecurityLevel,
) -> Result<Vec<u8>, CryptoError> {
    match level {
        SignatureSecurityLevel::Level2 => {
            let sk = dilithium2::SecretKey::from_bytes(secret_key)
                .map_err(|_| CryptoError::InvalidSecretKey)?;
            let signature = dilithium2::detached_sign(message, &sk);
            Ok(signature.as_bytes().to_vec())
        }
        SignatureSecurityLevel::Level3 => {
            let sk = dilithium3::SecretKey::from_bytes(secret_key)
                .map_err(|_| CryptoError::InvalidSecretKey)?;
            let signature = dilithium3::detached_sign(message, &sk);
            Ok(signature.as_bytes().to_vec())
        }
        SignatureSecurityLevel::Level5 => {
            let sk = dilithium5::SecretKey::from_bytes(secret_key)
                .map_err(|_| CryptoError::InvalidSecretKey)?;
            let signature = dilithium5::detached_sign(message, &sk);
            Ok(signature.as_bytes().to_vec())
        }
    }
}

/// Verify a signature using ML-DSA
///
/// # Arguments
/// * `message` - Original message bytes
/// * `signature` - Detached signature bytes
/// * `public_key` - Signer's public key
///
/// # Returns
/// * `true` if signature is valid
pub fn verify(message: &[u8], signature: &[u8], public_key: &[u8]) -> Result<bool, CryptoError> {
    verify_with_level(
        message,
        signature,
        public_key,
        SignatureSecurityLevel::Level3,
    )
}

/// Verify with explicit security level
pub fn verify_with_level(
    message: &[u8],
    signature: &[u8],
    public_key: &[u8],
    level: SignatureSecurityLevel,
) -> Result<bool, CryptoError> {
    match level {
        SignatureSecurityLevel::Level2 => {
            let pk = dilithium2::PublicKey::from_bytes(public_key)
                .map_err(|_| CryptoError::InvalidPublicKey)?;
            let sig = dilithium2::DetachedSignature::from_bytes(signature)
                .map_err(|_| CryptoError::InvalidSignature)?;
            match dilithium2::verify_detached_signature(&sig, message, &pk) {
                Ok(_) => Ok(true),
                Err(_) => Ok(false),
            }
        }
        SignatureSecurityLevel::Level3 => {
            let pk = dilithium3::PublicKey::from_bytes(public_key)
                .map_err(|_| CryptoError::InvalidPublicKey)?;
            let sig = dilithium3::DetachedSignature::from_bytes(signature)
                .map_err(|_| CryptoError::InvalidSignature)?;
            match dilithium3::verify_detached_signature(&sig, message, &pk) {
                Ok(_) => Ok(true),
                Err(_) => Ok(false),
            }
        }
        SignatureSecurityLevel::Level5 => {
            let pk = dilithium5::PublicKey::from_bytes(public_key)
                .map_err(|_| CryptoError::InvalidPublicKey)?;
            let sig = dilithium5::DetachedSignature::from_bytes(signature)
                .map_err(|_| CryptoError::InvalidSignature)?;
            match dilithium5::verify_detached_signature(&sig, message, &pk) {
                Ok(_) => Ok(true),
                Err(_) => Ok(false),
            }
        }
    }
}

/// Sign message with base64 encoded secret key
pub fn sign_base64(message: &[u8], secret_key_b64: &str) -> Result<Signature, CryptoError> {
    use base64::Engine;
    let secret_key = base64::engine::general_purpose::STANDARD
        .decode(secret_key_b64)
        .map_err(|_| CryptoError::InvalidKeyFormat)?;

    let signature_bytes = sign(message, &secret_key)?;
    Ok(Signature::new(signature_bytes))
}

/// Verify signature with base64 encoded inputs
pub fn verify_base64(
    message: &[u8],
    signature_b64: &str,
    public_key_b64: &str,
) -> Result<bool, CryptoError> {
    use base64::Engine;
    let signature = base64::engine::general_purpose::STANDARD
        .decode(signature_b64)
        .map_err(|_| CryptoError::InvalidSignature)?;
    let public_key = base64::engine::general_purpose::STANDARD
        .decode(public_key_b64)
        .map_err(|_| CryptoError::InvalidKeyFormat)?;

    verify(message, &signature, &public_key)
}

/// Sign a JSON-serializable object
pub fn sign_json<T: Serialize>(data: &T, secret_key: &[u8]) -> Result<Signature, CryptoError> {
    let json_bytes = serde_json::to_vec(data).map_err(|_| CryptoError::SerializationError)?;
    let signature_bytes = sign(&json_bytes, secret_key)?;
    Ok(Signature::new(signature_bytes))
}

/// Verify signature on a JSON-serializable object
pub fn verify_json<T: Serialize>(
    data: &T,
    signature: &Signature,
    public_key: &[u8],
) -> Result<bool, CryptoError> {
    let json_bytes = serde_json::to_vec(data).map_err(|_| CryptoError::SerializationError)?;
    verify(&json_bytes, &signature.signature, public_key)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_signature_roundtrip() {
        let keypair = SigningKeyPair::generate().unwrap();
        let message = b"Hello, quantum-safe world!";

        let signature = sign(message, &keypair.secret_key).unwrap();
        let is_valid = verify(message, &signature, &keypair.public_key).unwrap();

        assert!(is_valid);
    }

    #[test]
    fn test_signature_base64_roundtrip() {
        let keypair = SigningKeyPair::generate().unwrap();
        let pk_b64 = keypair.public_key_base64();
        let sk_b64 = keypair.secret_key_base64();

        let message = b"Test message for signing";
        let signature = sign_base64(message, &sk_b64).unwrap();
        let sig_b64 = signature.to_base64();

        let is_valid = verify_base64(message, &sig_b64, &pk_b64).unwrap();
        assert!(is_valid);
    }

    #[test]
    fn test_invalid_signature() {
        let keypair = SigningKeyPair::generate().unwrap();
        let other_keypair = SigningKeyPair::generate().unwrap();

        let message = b"Original message";
        let signature = sign(message, &keypair.secret_key).unwrap();

        // Verify with wrong public key
        let is_valid = verify(message, &signature, &other_keypair.public_key).unwrap();
        assert!(!is_valid);
    }

    #[test]
    fn test_tampered_message() {
        let keypair = SigningKeyPair::generate().unwrap();
        let message = b"Original message";
        let tampered = b"Tampered message";

        let signature = sign(message, &keypair.secret_key).unwrap();
        let is_valid = verify(tampered, &signature, &keypair.public_key).unwrap();

        assert!(!is_valid);
    }
}
