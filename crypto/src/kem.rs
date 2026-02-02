//! ML-KEM (CRYSTALS-Kyber) Key Encapsulation Mechanism
//! 
//! Implements NIST FIPS 203 ML-KEM for post-quantum secure key exchange.
//! Supports all three security levels:
//! - ML-KEM-512 (Level 1) - Lightweight, ~AES-128 equivalent
//! - ML-KEM-768 (Level 3) - Recommended, ~AES-192 equivalent
//! - ML-KEM-1024 (Level 5) - Maximum security, ~AES-256 equivalent

use pqcrypto_kyber::{kyber512, kyber768, kyber1024};
use pqcrypto_traits::kem::{PublicKey, SecretKey, SharedSecret, Ciphertext};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use crate::error::CryptoError;

/// Security level for ML-KEM
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum KemSecurityLevel {
    /// ML-KEM-512 (NIST Level 1) - Lightweight security
    Level1,
    /// ML-KEM-768 (NIST Level 3) - Recommended
    Level3,
    /// ML-KEM-1024 (NIST Level 5) - Maximum security
    Level5,
}

impl Default for KemSecurityLevel {
    fn default() -> Self {
        KemSecurityLevel::Level3
    }
}

impl KemSecurityLevel {
    /// Get the algorithm name for this security level
    pub fn algorithm_name(&self) -> &'static str {
        match self {
            KemSecurityLevel::Level1 => "ML-KEM-512",
            KemSecurityLevel::Level3 => "ML-KEM-768",
            KemSecurityLevel::Level5 => "ML-KEM-1024",
        }
    }
    
    /// Get key sizes for this security level
    pub fn key_sizes(&self) -> (usize, usize, usize) {
        // Returns (public_key_size, secret_key_size, ciphertext_size)
        match self {
            KemSecurityLevel::Level1 => (800, 1632, 768),
            KemSecurityLevel::Level3 => (1184, 2400, 1088),
            KemSecurityLevel::Level5 => (1568, 3168, 1568),
        }
    }
    
    /// Parse from string (e.g., "1", "3", "5" or "level1", "level3", "level5")
    pub fn from_str(s: &str) -> Result<Self, CryptoError> {
        match s.to_lowercase().trim() {
            "1" | "level1" | "l1" | "512" => Ok(KemSecurityLevel::Level1),
            "3" | "level3" | "l3" | "768" => Ok(KemSecurityLevel::Level3),
            "5" | "level5" | "l5" | "1024" => Ok(KemSecurityLevel::Level5),
            _ => Err(CryptoError::UnsupportedSecurityLevel),
        }
    }
}

/// ML-KEM key pair container
#[derive(Clone)]
pub struct KemKeyPair {
    pub public_key: Vec<u8>,
    pub secret_key: Vec<u8>,
    pub security_level: KemSecurityLevel,
}

impl KemKeyPair {
    /// Generate a new ML-KEM-768 key pair (default Level 3)
    pub fn generate() -> Result<Self, CryptoError> {
        Self::generate_with_level(KemSecurityLevel::Level3)
    }

    /// Generate key pair with specified security level
    pub fn generate_with_level(level: KemSecurityLevel) -> Result<Self, CryptoError> {
        match level {
            KemSecurityLevel::Level1 => {
                let (pk, sk) = kyber512::keypair();
                Ok(KemKeyPair {
                    public_key: pk.as_bytes().to_vec(),
                    secret_key: sk.as_bytes().to_vec(),
                    security_level: level,
                })
            }
            KemSecurityLevel::Level3 => {
                let (pk, sk) = kyber768::keypair();
                Ok(KemKeyPair {
                    public_key: pk.as_bytes().to_vec(),
                    secret_key: sk.as_bytes().to_vec(),
                    security_level: level,
                })
            }
            KemSecurityLevel::Level5 => {
                let (pk, sk) = kyber1024::keypair();
                Ok(KemKeyPair {
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
        
        Ok(KemKeyPair {
            public_key,
            secret_key,
            security_level: KemSecurityLevel::Level3,
        })
    }
}

/// Encapsulation result containing ciphertext and shared secret
#[derive(Clone)]
pub struct EncapsulationResult {
    pub ciphertext: Vec<u8>,
    pub shared_secret: Vec<u8>,
}

impl EncapsulationResult {
    /// Export ciphertext as base64
    pub fn ciphertext_base64(&self) -> String {
        base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &self.ciphertext)
    }
}

/// Encapsulate a shared secret using recipient's public key
/// 
/// # Arguments
/// * `public_key` - Recipient's ML-KEM public key
/// * `level` - Security level (determines key sizes)
/// 
/// # Returns
/// * `EncapsulationResult` containing ciphertext and shared secret
pub fn encapsulate(public_key: &[u8]) -> Result<EncapsulationResult, CryptoError> {
    encapsulate_with_level(public_key, KemSecurityLevel::Level3)
}

/// Encapsulate with explicit security level
pub fn encapsulate_with_level(public_key: &[u8], level: KemSecurityLevel) -> Result<EncapsulationResult, CryptoError> {
    match level {
        KemSecurityLevel::Level1 => {
            let pk = kyber512::PublicKey::from_bytes(public_key)
                .map_err(|_| CryptoError::InvalidPublicKey)?;
            let (shared_secret, ciphertext) = kyber512::encapsulate(&pk);
            Ok(EncapsulationResult {
                ciphertext: ciphertext.as_bytes().to_vec(),
                shared_secret: shared_secret.as_bytes().to_vec(),
            })
        }
        KemSecurityLevel::Level3 => {
            let pk = kyber768::PublicKey::from_bytes(public_key)
                .map_err(|_| CryptoError::InvalidPublicKey)?;
            let (shared_secret, ciphertext) = kyber768::encapsulate(&pk);
            Ok(EncapsulationResult {
                ciphertext: ciphertext.as_bytes().to_vec(),
                shared_secret: shared_secret.as_bytes().to_vec(),
            })
        }
        KemSecurityLevel::Level5 => {
            let pk = kyber1024::PublicKey::from_bytes(public_key)
                .map_err(|_| CryptoError::InvalidPublicKey)?;
            let (shared_secret, ciphertext) = kyber1024::encapsulate(&pk);
            Ok(EncapsulationResult {
                ciphertext: ciphertext.as_bytes().to_vec(),
                shared_secret: shared_secret.as_bytes().to_vec(),
            })
        }
    }
}

/// Decapsulate shared secret from ciphertext using secret key
/// 
/// # Arguments
/// * `ciphertext` - The encapsulated ciphertext
/// * `secret_key` - Recipient's ML-KEM secret key
/// 
/// # Returns
/// * Shared secret bytes
pub fn decapsulate(ciphertext: &[u8], secret_key: &[u8]) -> Result<Vec<u8>, CryptoError> {
    decapsulate_with_level(ciphertext, secret_key, KemSecurityLevel::Level3)
}

/// Decapsulate with explicit security level
pub fn decapsulate_with_level(ciphertext: &[u8], secret_key: &[u8], level: KemSecurityLevel) -> Result<Vec<u8>, CryptoError> {
    match level {
        KemSecurityLevel::Level1 => {
            let ct = kyber512::Ciphertext::from_bytes(ciphertext)
                .map_err(|_| CryptoError::InvalidCiphertext)?;
            let sk = kyber512::SecretKey::from_bytes(secret_key)
                .map_err(|_| CryptoError::InvalidSecretKey)?;
            let shared_secret = kyber512::decapsulate(&ct, &sk);
            Ok(shared_secret.as_bytes().to_vec())
        }
        KemSecurityLevel::Level3 => {
            let ct = kyber768::Ciphertext::from_bytes(ciphertext)
                .map_err(|_| CryptoError::InvalidCiphertext)?;
            let sk = kyber768::SecretKey::from_bytes(secret_key)
                .map_err(|_| CryptoError::InvalidSecretKey)?;
            let shared_secret = kyber768::decapsulate(&ct, &sk);
            Ok(shared_secret.as_bytes().to_vec())
        }
        KemSecurityLevel::Level5 => {
            let ct = kyber1024::Ciphertext::from_bytes(ciphertext)
                .map_err(|_| CryptoError::InvalidCiphertext)?;
            let sk = kyber1024::SecretKey::from_bytes(secret_key)
                .map_err(|_| CryptoError::InvalidSecretKey)?;
            let shared_secret = kyber1024::decapsulate(&ct, &sk);
            Ok(shared_secret.as_bytes().to_vec())
        }
    }
}

/// Encapsulate using base64 encoded public key
pub fn encapsulate_base64(public_key_b64: &str) -> Result<EncapsulationResult, CryptoError> {
    use base64::Engine;
    let public_key = base64::engine::general_purpose::STANDARD
        .decode(public_key_b64)
        .map_err(|_| CryptoError::InvalidKeyFormat)?;
    encapsulate(&public_key)
}

/// Decapsulate using base64 encoded inputs
pub fn decapsulate_base64(ciphertext_b64: &str, secret_key_b64: &str) -> Result<Vec<u8>, CryptoError> {
    use base64::Engine;
    let ciphertext = base64::engine::general_purpose::STANDARD
        .decode(ciphertext_b64)
        .map_err(|_| CryptoError::InvalidCiphertext)?;
    let secret_key = base64::engine::general_purpose::STANDARD
        .decode(secret_key_b64)
        .map_err(|_| CryptoError::InvalidKeyFormat)?;
    decapsulate(&ciphertext, &secret_key)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_kem_roundtrip_level1() {
        let keypair = KemKeyPair::generate_with_level(KemSecurityLevel::Level1).unwrap();
        let encap_result = encapsulate_with_level(&keypair.public_key, KemSecurityLevel::Level1).unwrap();
        let decap_secret = decapsulate_with_level(&encap_result.ciphertext, &keypair.secret_key, KemSecurityLevel::Level1).unwrap();
        assert_eq!(encap_result.shared_secret, decap_secret);
    }

    #[test]
    fn test_kem_roundtrip_level3() {
        let keypair = KemKeyPair::generate_with_level(KemSecurityLevel::Level3).unwrap();
        let encap_result = encapsulate_with_level(&keypair.public_key, KemSecurityLevel::Level3).unwrap();
        let decap_secret = decapsulate_with_level(&encap_result.ciphertext, &keypair.secret_key, KemSecurityLevel::Level3).unwrap();
        assert_eq!(encap_result.shared_secret, decap_secret);
    }

    #[test]
    fn test_kem_roundtrip_level5() {
        let keypair = KemKeyPair::generate_with_level(KemSecurityLevel::Level5).unwrap();
        let encap_result = encapsulate_with_level(&keypair.public_key, KemSecurityLevel::Level5).unwrap();
        let decap_secret = decapsulate_with_level(&encap_result.ciphertext, &keypair.secret_key, KemSecurityLevel::Level5).unwrap();
        assert_eq!(encap_result.shared_secret, decap_secret);
    }

    #[test]
    fn test_kem_key_sizes() {
        // Level 1
        let kp1 = KemKeyPair::generate_with_level(KemSecurityLevel::Level1).unwrap();
        assert_eq!(kp1.public_key.len(), 800);
        assert_eq!(kp1.secret_key.len(), 1632);
        
        // Level 3
        let kp3 = KemKeyPair::generate_with_level(KemSecurityLevel::Level3).unwrap();
        assert_eq!(kp3.public_key.len(), 1184);
        assert_eq!(kp3.secret_key.len(), 2400);
        
        // Level 5
        let kp5 = KemKeyPair::generate_with_level(KemSecurityLevel::Level5).unwrap();
        assert_eq!(kp5.public_key.len(), 1568);
        assert_eq!(kp5.secret_key.len(), 3168);
    }

    #[test]
    fn test_kem_base64_roundtrip() {
        let keypair = KemKeyPair::generate().unwrap();
        let pk_b64 = keypair.public_key_base64();
        let sk_b64 = keypair.secret_key_base64();
        
        let encap_result = encapsulate_base64(&pk_b64).unwrap();
        let ct_b64 = encap_result.ciphertext_base64();
        
        let decap_secret = decapsulate_base64(&ct_b64, &sk_b64).unwrap();
        
        assert_eq!(encap_result.shared_secret, decap_secret);
    }
    
    #[test]
    fn test_security_level_parsing() {
        assert_eq!(KemSecurityLevel::from_str("1").unwrap(), KemSecurityLevel::Level1);
        assert_eq!(KemSecurityLevel::from_str("level3").unwrap(), KemSecurityLevel::Level3);
        assert_eq!(KemSecurityLevel::from_str("L5").unwrap(), KemSecurityLevel::Level5);
        assert_eq!(KemSecurityLevel::from_str("768").unwrap(), KemSecurityLevel::Level3);
        assert!(KemSecurityLevel::from_str("invalid").is_err());
    }
}
